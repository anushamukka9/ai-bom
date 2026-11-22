"""CycloneDX export: turn a manifest into a CycloneDX 1.5 BOM.

The native manifest is the format I control, but most SBOM tooling
already speaks CycloneDX. This module translates one into the other
so an ai-bom scan can feed the tools a team already runs: dependency
trackers, vulnerability dashboards, and procurement reviews that ask
for a BOM file and mean CycloneDX when they say it.

Mapping, stated plainly so nobody has to guess:

- models become ``machine-learning-model`` components
- tools become ``library`` components
- MCP servers become ``application`` components
- datasets become ``data`` components
- prompts become ``file`` components

Every component keeps its ai-bom category, source, path, and digest
as CycloneDX properties, and a file hash becomes a CycloneDX hash
entry when one was recorded. The manifest digest and signature state
ride along as properties on the BOM metadata, so a reader can tell
which ai-bom manifest a BOM came from and check it against the
original. The export is one way: CycloneDX has no place for some
ai-bom fields, so importing a BOM back into a manifest is not
supported and this module does not pretend otherwise.
"""

from __future__ import annotations

import json
import re
import uuid

from ai_bom import __version__
from ai_bom.models import Component, Manifest

SPEC_VERSION = "1.5"

_CATEGORY_TYPES = {
    "models": "machine-learning-model",
    "tools": "library",
    "mcp_servers": "application",
    "datasets": "data",
    "prompts": "file",
}


def _bom_ref(comp: Component, index: int) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", comp.name).strip("-") or "component"
    return f"ai-bom:{comp.category}:{slug}:{index}"


def _component_to_cyclonedx(comp: Component, index: int) -> dict[str, object]:
    entry: dict[str, object] = {
        "type": _CATEGORY_TYPES[comp.category],
        "bom-ref": _bom_ref(comp, index),
        "name": comp.name,
    }
    if comp.version:
        entry["version"] = comp.version
    if comp.sha256:
        entry["hashes"] = [{"alg": "SHA-256", "content": comp.sha256}]
    properties: list[dict[str, str]] = [
        {"name": "ai-bom:category", "value": comp.category},
        {"name": "ai-bom:source", "value": comp.source},
        {"name": "ai-bom:digest", "value": comp.digest},
    ]
    if comp.path:
        properties.append({"name": "ai-bom:path", "value": comp.path})
    if comp.size_bytes is not None:
        properties.append({"name": "ai-bom:size_bytes", "value": str(comp.size_bytes)})
    entry["properties"] = properties
    return entry


def to_cyclonedx(manifest: Manifest) -> dict[str, object]:
    """Return the CycloneDX BOM for ``manifest`` as a plain dict."""
    serial = uuid.uuid5(uuid.NAMESPACE_URL, f"ai-bom:{manifest.digest}")
    metadata: dict[str, object] = {
        "tools": [
            {
                "vendor": "Anusha Mukka",
                "name": "ai-bom",
                "version": __version__,
            }
        ],
        "component": {
            "type": "application",
            "bom-ref": "ai-bom:project",
            "name": manifest.project,
        },
        "properties": [
            {"name": "ai-bom:digest", "value": manifest.digest},
            {"name": "ai-bom:schema_version", "value": manifest.schema_version},
            {
                "name": "ai-bom:signed",
                "value": "true" if manifest.signature else "false",
            },
        ],
    }
    if manifest.generated_at:
        metadata["timestamp"] = manifest.generated_at
    return {
        "bomFormat": "CycloneDX",
        "specVersion": SPEC_VERSION,
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": metadata,
        "components": [
            _component_to_cyclonedx(comp, index)
            for index, comp in enumerate(manifest.sorted_components())
        ],
    }


def manifest_to_cyclonedx_json(manifest: Manifest, indent: int | None = 2) -> str:
    """Serialize ``manifest`` as CycloneDX JSON text."""
    return json.dumps(to_cyclonedx(manifest), indent=indent, ensure_ascii=False) + "\n"
