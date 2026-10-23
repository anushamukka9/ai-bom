# The manifest format

A manifest is one JSON object. Canonical output uses sorted keys, so
two scans of an unchanged project produce byte-identical component
lists.

```json
{
  "schema_version": "1.0",
  "project": "example_project",
  "generated_at": "2026-10-22T23:47:00Z",
  "generator": "ai-bom 0.1.0",
  "digest": "9f2c...",
  "components": [
    {
      "name": "tickets.csv",
      "category": "datasets",
      "source": "data/tickets.csv",
      "version": null,
      "path": "data/tickets.csv",
      "size_bytes": 52,
      "sha256": "b3a1...",
      "digest": "77d0..."
    }
  ]
}
```

## Fields

Header:

- `schema_version`: the format version. `1.0` in this release.
- `project`: the scanned directory's name.
- `generated_at`: UTC timestamp of the scan. Metadata only; see the
  digest rules below.
- `generator`: the tool and version that produced the manifest.
- `digest`: the top-level SHA-256, described below.

Component:

- `name`: the component name. For file-backed components this is the
  file name; for packages it is the package display name; for MCP
  servers it is the server's key in its config.
- `category`: one of `models`, `tools`, `mcp_servers`, `datasets`,
  `prompts`.
- `source`: where the scanner found it, as a project relative path
  or a declaration file name.
- `version`: the declared or pinned version, or null when no source
  states one. The scanner never invents a version.
- `path`: project relative path for file-backed components, else
  null.
- `size_bytes` and `sha256`: recorded when a concrete file backs the
  component. For MCP servers, `sha256` covers that server's own
  config entry rather than the whole config file.
- `digest`: SHA-256 over the canonical serialization of the fields
  above.

## How the digests work

Canonical serialization means JSON with sorted keys and no optional
whitespace. The component digest is the SHA-256 of that form of the
component's fields. The manifest digest is the SHA-256 of that form
of an object holding `schema_version`, `project`, and the full
component list.

`generated_at` and `generator` are deliberately excluded from the
manifest digest. A rescan of an unchanged project at a later time
produces the same digest, which is what makes `diff` and digest
comparison useful. The trade-off is stated plainly in
[limitations.md](limitations.md): the timestamp itself is not
tamper-protected in v1.

## Signing: roadmap, not v1

v1 integrity is hash-only. Ed25519 signing of the manifest digest,
with a `sign` command and signature checking inside `verify`, is the
headline item for the next release. Nothing in v1 produces or checks
signatures, and the docs do not pretend otherwise.
