"""Signing demo: keygen, sign at build time, verify at deploy time.

Run: python examples/signing_demo.py

Generates a throwaway keypair, scans the bundled example project,
signs the manifest, and verifies it the way a deploy step would:
signature required, public key pinned. Then it edits a component
behind the manifest's back and shows the same verify failing, and
shows a manifest re-signed by an attacker's key failing against the
pinned public key.
"""

from ai_bom import generate_keypair, scan_project, sign_manifest, verify_manifest


def main() -> None:
    from pathlib import Path

    project = Path(__file__).resolve().parent / "example_project"
    private, public = generate_keypair()
    print("generated a throwaway Ed25519 keypair")

    manifest = scan_project(project)
    sign_manifest(manifest, private)
    print(f"signed manifest, digest {manifest.digest[:16]}...")

    result = verify_manifest(manifest, project, require_signature=True, public_key=public)
    print(f"deploy verify (signature required, key pinned): valid={result.valid}")
    assert result.valid

    tampered = scan_project(project)
    sign_manifest(tampered, private)
    tampered.components[0].name = "tampered"
    result = verify_manifest(tampered, project, require_signature=True, public_key=public)
    print(f"verify after a quiet edit to the manifest: valid={result.valid}")
    for problem in result.problems:
        print(f"  - {problem}")
    assert not result.valid

    attacker_private, _attacker_public = generate_keypair()
    forged = scan_project(project)
    forged.components[0].version = "9.9.9"
    for comp in forged.components:
        comp.digest = comp.compute_digest()
    sign_manifest(forged, attacker_private)
    result = verify_manifest(forged, project, require_signature=True, public_key=public)
    print(f"verify a manifest re-signed by another key: valid={result.valid}")
    for problem in result.problems:
        print(f"  - {problem}")
    assert not result.valid

    print("done. digests catch edits, signatures catch re-signing, pinning catches both.")


if __name__ == "__main__":
    main()
