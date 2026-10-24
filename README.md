# ai-bom

An AI Bill of Materials for agent apps. One command inventories your
models, tools, MCP servers, datasets, and prompts into a manifest
with a tamper-evident digest, and v0.2.0 signs it with Ed25519 so a
rewritten manifest cannot pass as the original. Know what your agent
is made of before it runs.

## Quickstart

```bash
pip install ai-bom
```

```bash
ai-bom scan ./my-agent-app --output ai-bom-manifest.json
ai-bom show ai-bom-manifest.json
ai-bom verify ai-bom-manifest.json ./my-agent-app
```

In Python:

```python
from ai_bom import scan_project, verify_manifest

manifest = scan_project("my-agent-app")
print(manifest.counts())
# {'models': 4, 'tools': 2, 'mcp_servers': 2, 'datasets': 2, 'prompts': 3}
print(manifest.digest)

result = verify_manifest(manifest, "my-agent-app")
assert result.valid
```

Thirty seconds, start to finish. See [docs/quickstart.md](docs/quickstart.md)
and [examples/quickstart.py](examples/quickstart.py).

## Why this exists

Every agent app I work on is quietly a pile of parts from other
people: a model from one provider, tools from three libraries, a
couple of MCP servers, a dataset someone downloaded last spring, and
prompts scattered across the repo. When something breaks, or when a
provider changes a model, or when a security review asks the simple
question "what is this thing actually made of", nobody has the list.

Software has had an answer to this for years: a bill of materials.
Agent apps mostly do not, because the parts do not sit in one
manifest file. They sit in dependency lists, MCP client configs,
prompt files, and data directories. ai-bom walks those declared
sources, writes the list down in one JSON manifest, and stamps it
with a SHA-256 digest so you can tell later whether the list, or the
files behind it, changed.

It pairs with my other repos in this series: llm-sentinel guards
what goes into the model, mcp-audit audits MCP server surfaces,
agent-policy-kit decides what the agent may do, agent-audit keeps
the tamper-evident record of what it did, and ai-bom writes down
what the agent is made of in the first place.

## What it finds

| Category | Where it looks |
|---|---|
| models | Declarations, known provider packages in dependencies and imports, `MODEL` style keys in `.env` files |
| tools | Declarations, known agent framework packages in dependencies and imports |
| mcp_servers | `mcpServers` entries in MCP client config JSON (Claude Desktop, Cursor, and friends) |
| datasets | Files under `data/` or `datasets/`, plus `.csv`, `.jsonl`, and `.parquet` files. Name, path, size, and hash only, never contents |
| prompts | `.prompt`, `.jinja`, `.j2`, and `.jinja2` files, plus anything under a `prompts/` directory |

You can also declare components by hand in an `aibom.json` or
`ai-bom.toml` file at the project root, for the parts no file gives
away, like a hosted model you call over HTTP. Discovery details are
in [docs/discovery.md](docs/discovery.md). Discovery is static and
conservative on purpose: it parses declared sources instead of
guessing, so if a signal is not in the tree, it is not in the
manifest.

## The manifest

Every component records its name, category, the source that named it,
a version when one is known, and, when a concrete file backs it, the
file path, size, and SHA-256. Each component also carries a digest
over its own fields, and the manifest carries one top-level digest
over everything in it. The format is documented in
[docs/manifest-format.md](docs/manifest-format.md).

Three more commands round it out:

```bash
ai-bom verify manifest.json ./my-agent-app   # fails loudly if a file or a digest changed
ai-bom diff old.json new.json                # added, removed, and changed components
ai-bom show manifest.json                    # a readable summary
```

Exit codes: 0 means fine, 1 means verify found a problem or diff
found differences, 2 means the inputs could not be read. Details in
[docs/cli.md](docs/cli.md).

## Signing

A digest alone proves a manifest matches itself. Anyone who can
rewrite the manifest can recompute its digests. A signature proves
the manifest came from whoever holds the private key:

```bash
ai-bom keygen --private ai-bom-private.key --public ai-bom-public.key
ai-bom scan ./my-agent-app --output ai-bom-manifest.json --sign-key ai-bom-private.key
ai-bom verify ai-bom-manifest.json ./my-agent-app --require-signature --public-key ai-bom-public.key
```

Sign at build time, verify at deploy time. `--require-signature`
fails closed on an unsigned manifest, and `--public-key` pins the
signer, so a manifest quietly re-signed with a different key fails
too. The private key never leaves the build side; the public key is
safe to commit next to the manifest. A ready to copy GitHub Actions
check lives in [examples/ci-verify-signed.yml](examples/ci-verify-signed.yml),
a runnable walkthrough in [examples/signing_demo.py](examples/signing_demo.py),
and the full story, including what a signature does not prove, in
[docs/signing.md](docs/signing.md). The Ed25519 implementation is
pure Python and stdlib-only, cross checked byte for byte against an
independent implementation in the tests.

## Benchmarks

Measured on this machine (see [benchmarks/results.md](benchmarks/results.md)
for the setup) against the bundled fixture project: 13 components
across all five categories.

| Benchmark | Result |
|---|---|
| Manifest build (fixture project, 13 components) | 1.43 ms average |
| Scan throughput | 702 scans/sec |
| Verify (manifest plus file hashes) | 2,977 verifies/sec |
| Sign a manifest digest (Ed25519) | 6.67 ms average, 150 signs/sec |
| Verify a signature (Ed25519) | 9.95 ms average, 101 verifies/sec |

Scanning is file walking plus hashing. A real project with large
datasets will be bound by hashing those files, which is the honest
cost of knowing they did not change. Signing is pure Python Ed25519
over one digest, so it costs a few milliseconds once per manifest,
not per file.

## Honest limitations

- **Static discovery only.** ai-bom reads files. It does not run
  your agent, trace its calls, or watch the network. A model your
  code downloads at runtime leaves no file signal and will not
  appear unless you declare it.
- **Hashing covers files, not remote services.** A hosted model or a
  remote MCP server is inventoried by name and declared version.
  Nothing here can prove the service behind that name did not change.
- **The known-package table is small.** Dependencies and imports are
  mapped through a table of common provider and framework packages.
  A package outside the table is not guessed at. Declare it in
  `aibom.json` instead.
- **Signatures prove a key, not a person.** Signing (v0.2.0) closes
  the re-signing gap for digests, but only when the deploy side pins
  the public key it trusts. A signature from an unpinned key proves
  someone signed it, not that the right someone did. Key handling
  is yours, and [docs/signing.md](docs/signing.md) says so plainly.
- **Dataset contents are never inspected.** The manifest records
  name, path, size, and hash. It cannot tell you a dataset is
  poisoned, licensed wrong, or full of PII.

Full list in [docs/limitations.md](docs/limitations.md). Read it
before you rely on this.

## Companions

Part of my agent security series:

- [llm-sentinel](https://github.com/anushamukka9/llm-sentinel) guards prompts going in.
- [mcp-audit](https://github.com/anushamukka9/mcp-audit) audits MCP server surfaces.
- [rag-canary](https://github.com/anushamukka9/rag-canary) watches retrieval for canary leaks.
- [agent-policy-kit](https://github.com/anushamukka9/agent-policy-kit) decides what agents may do.
- [agent-audit](https://github.com/anushamukka9/agent-audit) keeps the tamper-evident record.
- [output-contracts](https://github.com/anushamukka9/output-contracts) guards tool outputs coming out.
- [agent-scopes](https://github.com/anushamukka9/agent-scopes) issues short-lived scoped credentials.
- [agent-redteam](https://github.com/anushamukka9/agent-redteam) runs adversarial checks against agents.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Small and focused stays
small and focused: discovery sources need tests against fixture
projects, every feature documents what it cannot do, and there are
no em-dashes in this repo.

## License

MIT. See [LICENSE](LICENSE).
