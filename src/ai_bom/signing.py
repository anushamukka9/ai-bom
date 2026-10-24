"""Ed25519 signing for manifests: provenance on top of the digests.

The SHA-256 digests in a manifest detect edits only while the digest
you trust lives somewhere the manifest writer cannot reach. A
signature closes that gap. The person or pipeline that builds the
manifest signs its digest with a private key they keep; anyone at
deploy time verifies the signature with the public key, and a
rewritten manifest cannot be re-signed without the key.

What is signed is deliberately small: a domain separator plus the
manifest digest, not the whole file. The digest already covers every
component, so signing it signs the inventory. The signature block
itself, like ``generated_at``, sits outside the digest payload, so
adding or replacing a signature never changes the digest it covers.

Implementation note, stated plainly: Ed25519 here is a pure Python
implementation of RFC 8032 built on ``hashlib`` SHA-512. That keeps
the package stdlib-only, the same trade the rest of this series
makes. It is fast enough for signing a digest (a few milliseconds),
and it is not the code I would pick for signing a million messages
a second. Verification fails closed: malformed keys, malformed
signatures, and wrong lengths all return ``False``, never raise.
"""

from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from ai_bom.models import Manifest

ALGORITHM = "Ed25519"
_SIGNING_PREFIX = b"ai-bom:manifest:1:"

# Ed25519 parameters (RFC 8032, section 5.1).
_Q = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _Q - 2, _Q)) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)


def _sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def _inv(x: int) -> int:
    return pow(x, _Q - 2, _Q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _inv(_D * y * y + 1) % _Q
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q != 0:
        x = (x * _I) % _Q
    if x % 2 != 0:
        x = _Q - x
    return x


_BY = (4 * _inv(5)) % _Q
_BX = _xrecover(_BY)
_B = (_BX % _Q, _BY, 1, (_BX * _BY) % _Q)
_IDENTITY = (0, 1, 1, 0)


def _point_add(p: tuple, q: tuple) -> tuple:
    a = (p[1] - p[0]) * (q[1] - q[0]) % _Q
    b = (p[1] + p[0]) * (q[1] + q[0]) % _Q
    c = 2 * p[3] * q[3] * _D % _Q
    d = 2 * p[2] * q[2] % _Q
    e = (b - a) % _Q
    f = (d - c) % _Q
    g = (d + c) % _Q
    h = (b + a) % _Q
    return (e * f % _Q, g * h % _Q, f * g % _Q, e * h % _Q)


def _point_mul(p: tuple, e: int) -> tuple:
    result = _IDENTITY
    addend = p
    while e > 0:
        if e & 1:
            result = _point_add(result, addend)
        addend = _point_add(addend, addend)
        e >>= 1
    return result


def _encode_int(y: int) -> bytes:
    return bytes(y >> (8 * i) & 0xFF for i in range(32))


def _decode_int(data: bytes) -> int:
    return sum(b << (8 * i) for i, b in enumerate(data))


def _encode_point(p: tuple) -> bytes:
    x, y, z, _t = p
    inv_z = _inv(z)
    ax = x * inv_z % _Q
    ay = y * inv_z % _Q
    bits = [(ay >> i) & 1 for i in range(255)] + [ax & 1]
    return bytes(sum(bits[i * 8 + j] << j for j in range(8)) for i in range(32))


def _decode_point(data: bytes) -> tuple | None:
    if len(data) != 32:
        return None
    bits = [(data[i >> 3] >> (i & 7)) & 1 for i in range(256)]
    y = sum(bits[i] << i for i in range(255))
    if y >= _Q:
        return None
    x = _xrecover(y)
    if x & 1 != bits[255]:
        x = _Q - x
    point = (x, y, 1, x * y % _Q)
    # Reject points that are not on the curve.
    x2, y2 = x * x % _Q, y * y % _Q
    if (-x2 + y2 - 1 - _D * x2 * y2) % _Q != 0:
        return None
    return point


def _hint(data: bytes) -> int:
    h = _sha512(data)
    return sum(2**i * ((h[i >> 3] >> (i & 7)) & 1) for i in range(512))


def _expand_seed(seed: bytes) -> tuple[int, bytes]:
    h = _sha512(seed)
    a = 2**254 + sum(2**i * ((h[i >> 3] >> (i & 7)) & 1) for i in range(3, 254))
    return a, h[32:]


# Key and signature primitives. Keys are the raw RFC 8032 forms: a
# 32-byte seed is the private key, a 32-byte encoded point is the
# public key.


def generate_private_key() -> bytes:
    """Return a fresh 32-byte Ed25519 private key (seed)."""
    return os.urandom(32)


def derive_public_key(private_key: bytes) -> bytes:
    """Return the 32-byte public key for a 32-byte private key."""
    if len(private_key) != 32:
        raise ValueError("private key must be 32 bytes")
    a, _prefix = _expand_seed(private_key)
    return _encode_point(_point_mul(_B, a))


def sign(private_key: bytes, message: bytes) -> bytes:
    """Return the 64-byte Ed25519 signature of ``message``."""
    if len(private_key) != 32:
        raise ValueError("private key must be 32 bytes")
    a, prefix = _expand_seed(private_key)
    public = _encode_point(_point_mul(_B, a))
    r = _hint(prefix + message) % _L
    r_point = _point_mul(_B, r)
    r_encoded = _encode_point(r_point)
    s = (r + _hint(r_encoded + public + message) * a) % _L
    return r_encoded + _encode_int(s)


def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """Check a signature. Any malformed input is ``False``, never an error."""
    try:
        if len(public_key) != 32 or len(signature) != 64:
            return False
        a_point = _decode_point(public_key)
        if a_point is None:
            return False
        r_encoded = signature[:32]
        r_point = _decode_point(r_encoded)
        if r_point is None:
            return False
        s = _decode_int(signature[32:])
        if s >= _L:
            return False
        h = _hint(r_encoded + public_key + message)
        left = _point_mul(_B, s)
        right = _point_add(r_point, _point_mul(a_point, h))
        return _encode_point(left) == _encode_point(right)
    except Exception:
        return False


# Base64 and key-file helpers. Key files are one line of base64 with
# a header line naming the kind, so a file is recognizable on sight
# and a private key is never confused with a public one.

_PRIVATE_HEADER = "ai-bom ed25519 private key"
_PUBLIC_HEADER = "ai-bom ed25519 public key"


def encode_key(key: bytes) -> str:
    return base64.b64encode(key).decode("ascii")


def decode_key(text: str) -> bytes:
    return base64.b64decode(text.strip(), validate=True)


def save_private_key(path: Path | str, private_key: bytes) -> Path:
    if len(private_key) != 32:
        raise ValueError("private key must be 32 bytes")
    target = Path(path)
    target.write_text(f"{_PRIVATE_HEADER}\n{encode_key(private_key)}\n", encoding="utf-8")
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return target


def save_public_key(path: Path | str, public_key: bytes) -> Path:
    if len(public_key) != 32:
        raise ValueError("public key must be 32 bytes")
    target = Path(path)
    target.write_text(f"{_PUBLIC_HEADER}\n{encode_key(public_key)}\n", encoding="utf-8")
    return target


def _load_key(path: Path | str, header: str) -> bytes:
    lines = [
        line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if len(lines) != 2 or lines[0] != header:
        raise ValueError(f"not an ai-bom key file: {path}")
    key = decode_key(lines[1])
    if len(key) != 32:
        raise ValueError(f"key in {path} is not 32 bytes")
    return key


def load_private_key(path: Path | str) -> bytes:
    return _load_key(path, _PRIVATE_HEADER)


def load_public_key(path: Path | str) -> bytes:
    return _load_key(path, _PUBLIC_HEADER)


def generate_keypair() -> tuple[bytes, bytes]:
    """Return ``(private_key, public_key)`` as raw bytes."""
    private = generate_private_key()
    return private, derive_public_key(private)


# Manifest-level signing.


@dataclass
class Signature:
    """The signature block embedded in a signed manifest."""

    algorithm: str
    public_key: str
    signature: str
    signed_digest: str

    def to_dict(self) -> dict[str, object]:
        return {
            "algorithm": self.algorithm,
            "public_key": self.public_key,
            "signature": self.signature,
            "signed_digest": self.signed_digest,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Signature:
        return cls(
            algorithm=str(data.get("algorithm", "")),
            public_key=str(data.get("public_key", "")),
            signature=str(data.get("signature", "")),
            signed_digest=str(data.get("signed_digest", "")),
        )


def signing_message(digest: str) -> bytes:
    """The exact bytes signed for a manifest digest."""
    return _SIGNING_PREFIX + digest.encode("ascii")


def sign_manifest(manifest: Manifest, private_key: bytes) -> Signature:
    """Sign ``manifest`` in place and return its signature block.

    Refreshes the manifest digest first, so the signature always
    covers the contents as they stand at signing time.
    """
    digest = manifest.refresh_digest()
    signature = Signature(
        algorithm=ALGORITHM,
        public_key=encode_key(derive_public_key(private_key)),
        signature=encode_key(sign(private_key, signing_message(digest))),
        signed_digest=digest,
    )
    manifest.signature = signature.to_dict()
    return signature


def signature_problems(manifest: Manifest, expected_public_key: bytes | None = None) -> list[str]:
    """Problems with the manifest signature, or ``[]`` if it checks out.

    An unsigned manifest has no signature problems by this measure;
    requiring a signature is the caller's call (see
    ``verify_manifest(..., require_signature=True)``).
    """
    if manifest.signature is None:
        return []
    try:
        block = Signature.from_dict(manifest.signature)
    except Exception:
        return ["signature block is malformed"]
    problems: list[str] = []
    if block.algorithm != ALGORITHM:
        problems.append(f"unsupported signature algorithm: {block.algorithm or '(missing)'}")
        return problems
    if block.signed_digest != manifest.digest:
        problems.append("signature was made over a different manifest digest")
    if block.signed_digest != manifest.compute_digest():
        problems.append("signature does not cover the current manifest contents")
    try:
        public = decode_key(block.public_key)
        signature = decode_key(block.signature)
    except Exception:
        problems.append("signature block has invalid base64 key or signature data")
        return problems
    if expected_public_key is not None and public != expected_public_key:
        problems.append("signature public key does not match the expected public key")
        return problems
    if not verify(public, signing_message(block.signed_digest), signature):
        problems.append("signature verification failed: the signature does not match")
    return problems
