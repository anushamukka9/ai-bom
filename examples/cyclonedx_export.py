"""Export the example project as a CycloneDX BOM.

Run it with: python examples/cyclonedx_export.py

Scans the bundled example project, converts the manifest to
CycloneDX 1.5, prints a short summary, and writes the full BOM
next to this file as example-cyclonedx.json.
"""

from __future__ import annotations

import json
from pathlib import Path

from ai_bom import manifest_to_cyclonedx_json, scan_project, to_cyclonedx

HERE = Path(__file__).resolve().parent


def main() -> int:
    manifest = scan_project(HERE / "example_project")
    bom = to_cyclonedx(manifest)
    out = HERE / "example-cyclonedx.json"
    out.write_text(manifest_to_cyclonedx_json(manifest), encoding="utf-8")
    counts = manifest.counts()
    print(f"project: {manifest.project}")
    print(f"components: {sum(counts.values())} total, by category {counts}")
    print(f"cyclonedx: spec {bom['specVersion']}, serial {bom['serialNumber']}")
    print(f"wrote {out.name}: {len(json.dumps(bom))} bytes of CycloneDX JSON")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
