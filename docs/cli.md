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
```

Details that matter:

- `scan` prints only a one-line confirmation when `--output` is
  used. Without it, the manifest itself goes to stdout, so
  `ai-bom scan . > manifest.json` works.
- `verify` without a project path checks the manifest against
  itself: top-level digest, and every component digest. With a path
  it also re-hashes every file-backed component and re-checks every
  MCP server entry. Every problem it finds is printed by name.
- `diff` matches components by category, name, and path. A version
  bump and a hash change both count as `changed`, and the printed
  line says which fields moved.
- Manifests are plain JSON. Read them with `jq`, diff them with git,
  or load them with `Manifest.from_json`. The CLI is never the only
  way in.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success. Verify passed, or diff found no differences. |
| 1 | A finding: verify failed, or diff found differences. |
| 2 | Usage or input error: missing path, unreadable file, unparsable manifest. Nothing was checked. |

The 1 versus 2 split is deliberate. A CI step can treat 1 as "the
agent changed, review the diff" and 2 as "the pipeline is wired
wrong", and those should never look alike.
