"""The manifest data model: components, digests, and canonical JSON.

A manifest is a list of components in five categories plus a small
header. Two digests keep it honest:

- Each component carries a ``digest``: the SHA-256 of a canonical
  serialization of its own fields, including the file hash when a
  concrete file backs the component.
- The manifest carries one top-level ``digest``: the SHA-256 of a
  canonical serialization of the header fields and every component.

``generated_at`` and ``generator`` are metadata. They are stored in
the file but deliberately left out of the digest payload, so a fresh
timestamp never invalidates a manifest whose contents did not change.
Editing any component field, or the digest itself, breaks the digest
check in ``verify``.

An optional ``signature`` block (see ``ai_bom.signing``) is metadata
in the same way: it is stored in the file, left out of the digest
payload, and it signs the digest, so adding one never changes the
digest it covers.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

SCHEMA_VERSION = "1.0"

CATEGORIES = ("models", "tools", "mcp_servers", "datasets", "prompts")

_CATEGORY_ORDER = {name: idx for idx, name in enumerate(CATEGORIES)}


def canonical_json(obj: object) -> str:
    """Serialize ``obj`` deterministically: sorted keys, no spaces."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Component:
    """One inventoried thing: a model, tool, MCP server, dataset, or prompt."""

    name: str
    category: str
    source: str
    version: str | None = None
    path: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    digest: str = ""

    def __post_init__(self) -> None:
        if self.category not in CATEGORIES:
            raise ValueError(f"unknown category {self.category!r}")
        if not self.digest:
            self.digest = self.compute_digest()

    def key(self) -> tuple[str, str, str]:
        """Identity used for dedup and diff.

        Category plus name plus path. The path matters because two
        prompt files can share a filename in different directories,
        and the name matters because one MCP config file holds many
        servers.
        """
        return (self.category, self.name.lower(), self.path or "")

    def _payload(self) -> dict[str, object]:
        return {
            "name": self.name,
            "category": self.category,
            "source": self.source,
            "version": self.version,
            "path": self.path,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }

    def compute_digest(self) -> str:
        return sha256_text(canonical_json(self._payload()))

    def to_dict(self) -> dict[str, object]:
        data = self._payload()
        data["digest"] = self.digest
        return data

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Component:
        return cls(
            name=str(data["name"]),
            category=str(data["category"]),
            source=str(data.get("source", "")),
            version=data.get("version"),  # type: ignore[arg-type]
            path=data.get("path"),  # type: ignore[arg-type]
            size_bytes=data.get("size_bytes"),  # type: ignore[arg-type]
            sha256=data.get("sha256"),  # type: ignore[arg-type]
            digest=str(data.get("digest", "")),
        )


def _component_sort_key(comp: Component) -> tuple[int, str, str]:
    return (_CATEGORY_ORDER[comp.category], comp.name.lower(), comp.path or "")


@dataclass
class Manifest:
    """A full inventory of one project at one moment."""

    project: str
    components: list[Component] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION
    generated_at: str = ""
    generator: str = ""
    digest: str = ""
    signature: dict | None = None

    def sorted_components(self) -> list[Component]:
        return sorted(self.components, key=_component_sort_key)

    def counts(self) -> dict[str, int]:
        result = {name: 0 for name in CATEGORIES}
        for comp in self.components:
            result[comp.category] += 1
        return result

    def _digest_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "project": self.project,
            "components": [comp.to_dict() for comp in self.sorted_components()],
        }

    def compute_digest(self) -> str:
        return sha256_text(canonical_json(self._digest_payload()))

    def refresh_digest(self) -> str:
        self.digest = self.compute_digest()
        return self.digest

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "schema_version": self.schema_version,
            "project": self.project,
            "generated_at": self.generated_at,
            "generator": self.generator,
            "digest": self.digest,
            "components": [comp.to_dict() for comp in self.sorted_components()],
        }
        if self.signature is not None:
            data["signature"] = self.signature
        return data

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False) + "\n"

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Manifest:
        raw_components = data.get("components", [])
        if not isinstance(raw_components, list):
            raise ValueError("manifest components must be a list")
        components = [Component.from_dict(item) for item in raw_components]
        raw_signature = data.get("signature")
        return cls(
            project=str(data.get("project", "")),
            components=components,
            schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
            generated_at=str(data.get("generated_at", "")),
            generator=str(data.get("generator", "")),
            digest=str(data.get("digest", "")),
            signature=raw_signature if isinstance(raw_signature, dict) else None,
        )

    @classmethod
    def from_json(cls, text: str) -> Manifest:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("manifest JSON must be an object")
        return cls.from_dict(data)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Manifest):
            return NotImplemented
        return (
            self.project == other.project
            and self.schema_version == other.schema_version
            and [comp.to_dict() for comp in self.sorted_components()]
            == [comp.to_dict() for comp in other.sorted_components()]
        )
