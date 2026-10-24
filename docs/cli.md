# CLI

The CLI is a thin shell over the library, for pipelines and for
harnesses that are not Python.

```bash
ai-bom scan ./my-agent-app                            # manifest JSON to stdout
ai-bom scan ./my-agent-app --output manifest.json     # manifest JSON to a file
ai-bom scan ./my-agent-app --format markdown          # a readable table instead
ai-bom show manifest.json                             # summary: counts, digest, components
ai-bom verify manifest.json                           # internal digest checks only
ai-bom verify manifest.json ./my-agent-app            # digests plus every recorded file hash
ai-bom diff old.json new.json                         # added, removed, changed
ai-bom diff old.json new.json --format json           # the same, machine readable
ai-bom keygen                                         # an Ed25519 keypair in the current directory
ai-bom scan ./app -o manifest.json --sign-key ai-bom-private.key   # scan and sign in one step
ai-bom sign manifest.json --key ai-bom-private.key    # sign a manifest you already have
ai-bom verify manifest.json ./app --require-signature --public-key ai-bom-public.key
```

Details that matter:

- `scan` prints only a one-line confirmation when `--output` is
  used. Without it, the manifest itself goes to stdout, so
  `ai-bom scan . > manifest.json` works.
- `verify` without a project path checks the manifest against
  itself: top-level digest, and every component digest. With a path
  it also re-hashes every file-backed component and re-checks every
  MCP server entry. Every problem it finds is printed by name.
- A signed manifest is signature-checked by every `verify`, with no
  flag needed: a bad, malformed, or stale signature fails the run.
  `--require-signature` also fails an unsigned manifest, which is
  the deploy-time posture you want, and `--public-key FILE` pins
  the signer so a manifest re-signed with a different key fails too.
- `keygen` refuses to overwrite existing key files unless you pass
  `--force`, because quietly replacing a private key breaks every
  deploy check pinned to the old public key. `sign` writes in place
  unless `--output` says otherwise.
- `diff` matches components by category, name, and path. A version
  bump and a hash change both count as `changed`, and the printed
  line says which fields moved.
- Manifests are plain JSON. Read them with `jq`, diff them with git,
  or load them with `Manifest.from_json`. The CLI is never the only
  way in.
- Signing keys are plain text too: a header line and one line of
  base64, private and public in separate files so they are hard to
  confuse. The signing guide is [signing.md](signing.md).

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success. Verify passed, or diff found no differences. |
| 1 | A finding: verify failed, or diff found differences. |
| 2 | Usage or input error: missing path, unreadable file, unparsable manifest. Nothing was checked. |

The 1 versus 2 split is deliberate. A CI step can treat 1 as "the
agent changed, review the diff" and 2 as "the pipeline is wired
wrong", and those should never look alike.
