# Quickstart

## Install

```bash
pip install ai-bom
```

## The thirty-second version

```bash
ai-bom scan ./my-agent-app --output ai-bom-manifest.json
ai-bom show ai-bom-manifest.json
ai-bom verify ai-bom-manifest.json ./my-agent-app
```

The scan walks the project once and writes one JSON manifest: every
model, tool, MCP server, dataset, and prompt it can find in declared
sources, each with the source that named it and a SHA-256 for the
files behind it. Verify re-checks the manifest digest and every
recorded file hash, and fails loudly if anything moved.

In Python, the same thing looks like this:

```python
from ai_bom import scan_project, verify_manifest

manifest = scan_project("my-agent-app")
print(manifest.counts())
print(manifest.to_json())

result = verify_manifest(manifest, "my-agent-app")
if not result.valid:
    for problem in result.problems:
        print(problem)
```

## Try it on the bundled example

```bash
python examples/quickstart.py
ai-bom scan examples/example_project --format markdown
```

The example project is a tiny fake support agent. Its README lists
exactly what a scan should find, and the test suite holds the
scanner to that list.

## Sign it, if anyone downstream trusts it

A digest catches edits only while the digest itself is somewhere
safe. If a manifest travels to another team or another pipeline,
sign it at build time and verify the signature at deploy time:

```bash
ai-bom keygen --private ai-bom-private.key --public ai-bom-public.key
ai-bom scan ./my-agent-app --output ai-bom-manifest.json --sign-key ai-bom-private.key
ai-bom verify ai-bom-manifest.json ./my-agent-app --require-signature --public-key ai-bom-public.key
```

Keep the private key with your build secrets. The public key is
safe to commit. The full guide is [signing.md](signing.md).

## What to do with a manifest

- Commit it. A manifest in version control turns "what changed in
  the agent" into a diff you can read in review.
- Verify it in CI. `ai-bom verify` exits 1 when a hashed file or a
  digest does not match, which is the tripwire you want when a
  prompt or a dataset changes without a manifest update.
- Diff releases. `ai-bom diff old.json new.json` reports added,
  removed, and changed components between two scans.

## Next

- [discovery.md](discovery.md): every signal the scanner reads, and
  the ones it deliberately ignores.
- [manifest-format.md](manifest-format.md): the schema and how the
  digests are computed.
- [cli.md](cli.md): the commands and their exit codes.
- [signing.md](signing.md): Ed25519 signing, key handling, and the
  deploy-time check that fails closed.
- [limitations.md](limitations.md): what this does not do. Read it.
