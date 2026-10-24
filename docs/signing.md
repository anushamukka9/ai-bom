# Signing and verification

A digest tells you a manifest matches itself. A signature tells you
who made it, or at least who held the key. That difference matters
at deploy time: anyone who can rewrite a manifest can also recompute
its SHA-256 digests and hand you a self-consistent fake. They cannot
re-sign it without the private key.

## The flow

At build time, where the manifest is made:

```bash
ai-bom keygen --private ai-bom-private.key --public ai-bom-public.key
ai-bom scan ./my-agent-app --output ai-bom-manifest.json --sign-key ai-bom-private.key
```

Or sign a manifest you already have:

```bash
ai-bom sign ai-bom-manifest.json --key ai-bom-private.key
```

At deploy time, where the manifest is consumed:

```bash
ai-bom verify ai-bom-manifest.json ./my-agent-app --require-signature --public-key ai-bom-public.key
```

`--require-signature` fails closed: an unsigned manifest exits 1
instead of passing on digests alone. `--public-key` pins the signer:
a manifest re-signed with a different key also exits 1, even though
its own embedded signature is valid for that other key. In CI, those
two flags together are the whole check. See
`examples/ci-verify-signed.yml` for a ready to copy GitHub Actions
job.

In Python:

```python
from ai_bom import generate_keypair, scan_project, sign_manifest, verify_manifest
from ai_bom.signing import load_public_key

private, public = generate_keypair()
manifest = scan_project("my-agent-app")
sign_manifest(manifest, private)

result = verify_manifest(
    manifest, "my-agent-app", require_signature=True, public_key=public
)
assert result.valid
```

## What gets signed

The signature covers a short message: the text
`ai-bom:manifest:1:` followed by the manifest digest. The digest
already covers every component, so signing it signs the whole
inventory. The signature block itself sits outside the digest
payload, next to `generated_at`, so signing a manifest never changes
the digest it covers.

A signed manifest carries one extra field:

```json
"signature": {
  "algorithm": "Ed25519",
  "public_key": "base64 of the 32 byte public key",
  "signature": "base64 of the 64 byte signature",
  "signed_digest": "the manifest digest at signing time"
}
```

`verify` checks a signed manifest in this order, and any failure is
a finding, not a warning: the algorithm is Ed25519, `signed_digest`
matches both the stored digest and a fresh digest over the contents,
the public key matches the pinned key when one is given, and the
Ed25519 signature verifies over the signed digest. Malformed blocks,
bad base64, and wrong lengths all fail the same way. Nothing about a
bad signature is ever a pass.

## Keys

`keygen` writes two small text files: a header line saying which
kind of key it is, and one line of base64. The private key file is
written with owner-only permissions (0600) where the system allows
it, and `.gitignore` in this repo already excludes
`ai-bom-private.key` and any `*-private.key` file.

- Keep the private key where your build secrets live: a CI secret, a
  secrets manager, a file only the build account can read. Never in
  the repo, never in the manifest, never pasted into an issue.
- The public key is safe to commit, publish, and pin in deploy
  configs. Pinning it is what makes verification mean something.
- Rotating is easy and local: run `keygen` again, sign new manifests
  with the new key, and update the pinned public key in the deploy
  check. Old manifests keep verifying against the old public key for
  as long as you keep it around.

## What a signature does not prove

- It proves the holder of the private key signed this digest. It
  does not prove the holder is who you think they are. That part is
  key distribution, and it is yours: hand the public key over a
  channel you trust, or pin its value in a config the signer cannot
  change.
- It does not prove the inventory is complete or correct. A signed
  manifest of a badly scanned project is a well signed list of the
  wrong things. Signing is provenance, not accuracy; the discovery
  limitations in [limitations.md](limitations.md) still apply.
- It does not encrypt anything. The manifest stays plain JSON,
  readable by anyone, which is the point.

## The implementation, plainly

Ed25519 is implemented in pure Python in `ai_bom/signing.py`,
following RFC 8032 and built only on `hashlib` SHA-512, so the
package stays stdlib-only. A sign takes a few milliseconds and a
verify about the same order; the measured numbers are in
[../benchmarks/results.md](../benchmarks/results.md). The test suite
pins the implementation to a fixed-seed vector that was cross
checked byte for byte against an independent Ed25519 implementation,
so it speaks the same Ed25519 as everyone else, not a private
dialect. If you need to verify a manifest outside Python, any
standard Ed25519 tool can do it: decode the two base64 fields and
check the signature over `ai-bom:manifest:1:` plus the digest.
