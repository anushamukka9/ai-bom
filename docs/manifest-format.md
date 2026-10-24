# The manifest format

A manifest is one JSON object. Canonical output uses sorted keys, so
two scans of an unchanged project produce byte-identical component
lists.

```json
{
  "schema_version": "1.0",
  "project": "example_project",
  "generated_at": "2026-10-22T23:47:00Z",
  "generator": "ai-bom 0.2.0",
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
- `signature`: optional Ed25519 signature block, described under
  Signing below. Absent when the manifest is unsigned.

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

## Signing

Since v0.2.0 a manifest may carry one more top-level field:

```json
"signature": {
  "algorithm": "Ed25519",
  "public_key": "base64 of the 32 byte public key",
  "signature": "base64 of the 64 byte signature",
  "signed_digest": "the manifest digest at signing time"
}
```

The field is absent on unsigned manifests, so old manifests read
exactly as before. The signature is computed over the text
`ai-bom:manifest:1:` followed by the manifest digest, using
Ed25519 as specified in RFC 8032. Like `generated_at`, the
signature block sits outside the digest payload, so signing never
changes the digest it covers. Verification of the signature lives
inside `verify`, fails closed on any malformed or mismatched block,
and is described in full in [signing.md](signing.md).
