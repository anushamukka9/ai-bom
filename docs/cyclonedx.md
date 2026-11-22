# CycloneDX export

Most SBOM tooling already speaks CycloneDX. Since v0.3.0, ai-bom can
export any manifest in CycloneDX 1.5 format, so a scan can feed the
dependency trackers, vulnerability dashboards, and procurement
reviews a team already runs, without anyone writing a converter.

## Export an existing manifest

```bash
ai-bom export manifest.json --output bom.cdx.json
ai-bom export manifest.json          # CycloneDX JSON to stdout
```

## Or export straight from a scan

```bash
ai-bom scan ./my-agent-app --format cyclonedx --output bom.cdx.json
```

In Python:

```python
from ai_bom import scan_project, to_cyclonedx
import json

manifest = scan_project("my-agent-app")
bom = to_cyclonedx(manifest)
print(json.dumps(bom, indent=2))
```

## How components map

| ai-bom category | CycloneDX type |
|---|---|
| models | machine-learning-model |
| tools | library |
| mcp_servers | application |
| datasets | data |
| prompts | file |

Every exported component keeps its ai-bom category, source, path,
and per-component digest as CycloneDX properties (`ai-bom:category`,
`ai-bom:source`, `ai-bom:path`, `ai-bom:digest`), and a recorded file
hash becomes a CycloneDX `SHA-256` hash entry. The BOM metadata
names the scanned project, records the tool that produced it, and
carries the manifest digest and signed-or-not state as properties,
so a reader can match a BOM back to the exact ai-bom manifest it
came from. The serial number is derived from the manifest digest,
so re-exporting an unchanged manifest produces the same serial
number, and a changed manifest gets a new one.

## Honest limitations

- The export is one way. CycloneDX has no place for some ai-bom
  fields, so there is no BOM-to-manifest import, and I do not plan
  to fake one.
- The export covers components and hashes. It does not add
  vulnerability, license, or supplier data that ai-bom never
  collected in the first place.
- An example export of the bundled example project lives at
  `examples/example-cyclonedx.json`, and `examples/cyclonedx_export.py`
  shows the scan, export, and write steps end to end.
