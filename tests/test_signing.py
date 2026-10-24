"""Tests for Ed25519 signing: primitives, key files, and manifests.

The fixed-seed vector below was cross checked against an independent
Ed25519 implementation during development: for the seed
``bytes(range(32))`` and the message ``b"hello world"``, the public
key and the deterministic signature must match byte for byte. That
pins the pure Python implementation to the real Ed25519, not just
to itself.
"""

import json
import os
import stat
from pathlib import Path

import pytest

from ai_bom.cli import EXIT_FINDINGS, EXIT_OK, EXIT_USAGE, main
from ai_bom.discovery import scan_project
from ai_bom.fixture import build_fixture_project
from ai_bom.models import Manifest
from ai_bom.signing import (
    decode_key,
    derive_public_key,
    encode_key,
    generate_keypair,
    load_private_key,
    load_public_key,
    save_private_key,
    save_public_key,
    sign,
    sign_manifest,
    signature_problems,
    verify,
)
from ai_bom.verify import verify_manifest

FIXED_SEED = bytes(range(32))
FIXED_PUBLIC = "03a107bff3ce10be1d70dd18e74bc09967e4d6309ba50d5f1ddc8664125531b8"
FIXED_SIGNATURE = (
    "c9e88a06c88855aa75f90bcfdc5a87b76a99c0d2044114b8931e72089e7b8c7a"
    "c6b4a9776b57326f2d781aa8da8821fe6b4c7296fde0b63ca24d7f6343ac6a0a"
)


@pytest.fixture
def project(tmp_path):
    return build_fixture_project(tmp_path / "fixture")


@pytest.fixture
def keypair():
    return generate_keypair()


def test_fixed_seed_vector_matches_reference():
    assert derive_public_key(FIXED_SEED).hex() == FIXED_PUBLIC
    assert sign(FIXED_SEED, b"hello world").hex() == FIXED_SIGNATURE


def test_sign_verify_roundtrip(keypair):
    private, public = keypair
    signature = sign(private, b"a manifest digest")
    assert len(signature) == 64
    assert verify(public, b"a manifest digest", signature)


def test_signing_is_deterministic(keypair):
    private, _public = keypair
    assert sign(private, b"same") == sign(private, b"same")


def test_verify_rejects_tampered_message(keypair):
    private, public = keypair
    signature = sign(private, b"original")
    assert not verify(public, b"edited", signature)


def test_verify_rejects_wrong_key(keypair):
    private, _public = keypair
    _other_private, other_public = generate_keypair()
    signature = sign(private, b"data")
    assert not verify(other_public, b"data", signature)


def test_verify_fails_closed_on_malformed_input(keypair):
    _private, public = keypair
    assert not verify(public, b"data", b"")
    assert not verify(public, b"data", bytes(64))
    assert not verify(b"", b"data", bytes(64))
    assert not verify(bytes(32), b"data", bytes(64))
    assert not verify(public, b"data", bytes(63))


def test_bad_key_lengths_raise():
    with pytest.raises(ValueError):
        derive_public_key(b"short")
    with pytest.raises(ValueError):
        sign(b"short", b"data")


def test_key_files_roundtrip(tmp_path, keypair):
    private, public = keypair
    private_path = save_private_key(tmp_path / "signing-private.key", private)
    public_path = save_public_key(tmp_path / "signing-public.key", public)
    assert load_private_key(private_path) == private
    assert load_public_key(public_path) == public
    if os.name == "posix":
        mode = stat.S_IMODE(Path(private_path).stat().st_mode)
        assert mode == 0o600


def test_key_files_reject_the_wrong_kind(tmp_path, keypair):
    private, public = keypair
    public_path = save_public_key(tmp_path / "signing-public.key", public)
    with pytest.raises(ValueError):
        load_private_key(public_path)
    private_path = save_private_key(tmp_path / "signing-private.key", private)
    with pytest.raises(ValueError):
        load_public_key(private_path)


def test_encode_decode_key_roundtrip(keypair):
    _private, public = keypair
    assert decode_key(encode_key(public)) == public


def test_sign_manifest_and_verify(project, keypair):
    private, _public = keypair
    manifest = scan_project(project)
    digest_before = manifest.digest
    block = sign_manifest(manifest, private)
    assert manifest.digest == digest_before
    assert block.signed_digest == digest_before
    assert signature_problems(manifest) == []
    result = verify_manifest(manifest, project)
    assert result.valid, result.problems


def test_signed_manifest_survives_json_roundtrip(project, keypair, tmp_path):
    private, _public = keypair
    manifest = scan_project(project)
    sign_manifest(manifest, private)
    path = tmp_path / "signed.json"
    path.write_text(manifest.to_json(), encoding="utf-8")
    loaded = Manifest.from_json(path.read_text(encoding="utf-8"))
    assert loaded.signature == manifest.signature
    assert verify_manifest(loaded, project).valid


def test_unsigned_manifest_has_no_signature_problems(project):
    manifest = scan_project(project)
    assert manifest.signature is None
    assert signature_problems(manifest) == []
    assert verify_manifest(manifest, project).valid


def test_require_signature_fails_closed_on_unsigned(project):
    manifest = scan_project(project)
    result = verify_manifest(manifest, project, require_signature=True)
    assert not result.valid
    assert any("not signed" in problem for problem in result.problems)


def test_tampered_signed_manifest_fails(project, keypair):
    private, _public = keypair
    manifest = scan_project(project)
    sign_manifest(manifest, private)
    manifest.components[0].name = "tampered"
    result = verify_manifest(manifest, project)
    assert not result.valid
    assert any("signature" in problem for problem in result.problems)


def test_resigning_attack_fails_against_pinned_public_key(project, keypair):
    private, public = keypair
    manifest = scan_project(project)
    sign_manifest(manifest, private)
    # An attacker edits the inventory, recomputes the digests, and
    # re-signs with their own key. The embedded signature verifies
    # against the attacker's key, so only pinning the expected
    # public key catches it.
    attacker_private, _attacker_public = generate_keypair()
    manifest.components[0].version = "9.9.9"
    for comp in manifest.components:
        comp.digest = comp.compute_digest()
    sign_manifest(manifest, attacker_private)
    assert signature_problems(manifest) == []
    result = verify_manifest(manifest, project, public_key=public)
    assert not result.valid
    assert any("expected public key" in problem for problem in result.problems)


def test_wrong_pinned_public_key_fails(project, keypair):
    private, _public = keypair
    manifest = scan_project(project)
    sign_manifest(manifest, private)
    _other_private, other_public = generate_keypair()
    result = verify_manifest(manifest, project, public_key=other_public)
    assert not result.valid


def test_signature_over_stale_digest_fails(project, keypair):
    private, _public = keypair
    manifest = scan_project(project)
    sign_manifest(manifest, private)
    manifest.signature["signed_digest"] = "0" * 64
    problems = signature_problems(manifest)
    assert problems


def test_malformed_signature_block_fails_closed(project):
    manifest = scan_project(project)
    manifest.signature = {
        "algorithm": "Ed25519",
        "public_key": "not base64!!!",
        "signature": "also not base64!!!",
        "signed_digest": manifest.digest,
    }
    assert not verify_manifest(manifest, project).valid


def test_unsupported_algorithm_fails_closed(project, keypair):
    private, _public = keypair
    manifest = scan_project(project)
    sign_manifest(manifest, private)
    manifest.signature["algorithm"] = "RSA-4096"
    assert not verify_manifest(manifest, project).valid


@pytest.fixture
def cli_keys(tmp_path):
    private = tmp_path / "ai-bom-private.key"
    public = tmp_path / "ai-bom-public.key"
    assert main(["keygen", "--private", str(private), "--public", str(public)]) == EXIT_OK
    return private, public


def test_cli_keygen_refuses_overwrite(cli_keys):
    private, public = cli_keys
    assert main(["keygen", "--private", str(private), "--public", str(public)]) == EXIT_USAGE
    assert (
        main(["keygen", "--private", str(private), "--public", str(public), "--force"]) == EXIT_OK
    )


def test_cli_sign_verify_roundtrip(project, cli_keys, tmp_path, capsys):
    private, public = cli_keys
    manifest_file = tmp_path / "manifest.json"
    assert main(["scan", str(project), "--output", str(manifest_file)]) == EXIT_OK
    assert main(["sign", str(manifest_file), "--key", str(private)]) == EXIT_OK
    data = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert data["signature"]["algorithm"] == "Ed25519"
    assert (
        main(
            [
                "verify",
                str(manifest_file),
                str(project),
                "--require-signature",
                "--public-key",
                str(public),
            ]
        )
        == EXIT_OK
    )
    assert "signature verified" in capsys.readouterr().out


def test_cli_verify_require_signature_on_unsigned(project, tmp_path):
    manifest_file = tmp_path / "manifest.json"
    assert main(["scan", str(project), "--output", str(manifest_file)]) == EXIT_OK
    assert main(["verify", str(manifest_file), "--require-signature"]) == EXIT_FINDINGS


def test_cli_scan_sign_key(project, cli_keys, tmp_path):
    private, public = cli_keys
    signed = tmp_path / "signed.json"
    assert (
        main(["scan", str(project), "--output", str(signed), "--sign-key", str(private)]) == EXIT_OK
    )
    assert (
        main(["verify", str(signed), "--public-key", str(public), "--require-signature"]) == EXIT_OK
    )


def test_cli_sign_with_missing_key_is_usage_error(project, tmp_path):
    manifest_file = tmp_path / "manifest.json"
    assert main(["scan", str(project), "--output", str(manifest_file)]) == EXIT_OK
    missing = tmp_path / "nope.key"
    assert main(["sign", str(manifest_file), "--key", str(missing)]) == EXIT_USAGE


def test_cli_verify_with_wrong_public_key(project, cli_keys, tmp_path):
    private, _public = cli_keys
    manifest_file = tmp_path / "manifest.json"
    assert (
        main(["scan", str(project), "--output", str(manifest_file), "--sign-key", str(private)])
        == EXIT_OK
    )
    other_private = tmp_path / "other-private.key"
    other_public = tmp_path / "other-public.key"
    assert (
        main(["keygen", "--private", str(other_private), "--public", str(other_public)]) == EXIT_OK
    )
    assert main(["verify", str(manifest_file), "--public-key", str(other_public)]) == EXIT_FINDINGS
