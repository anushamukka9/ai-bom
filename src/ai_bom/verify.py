"""Verification: does this manifest still describe reality?

Two layers, both cheap:

1. Internal consistency. The manifest digest must match a fresh
   digest over its contents, and every component digest must match
   its fields. This catches edits to the manifest file itself.
2. File checks (when a project root is given). Every file-backed
   component must still exist at its recorded path, with the recorded
   size and SHA-256. This catches edits to the project after the scan.

A manifest that passes layer 1 but was never pinned anywhere proves
only that it is self-consistent. Anyone who can rewrite the manifest
can recompute its digests. Keep the digest somewhere the manifest
writer cannot reach if you need the stronger claim. Ed25519 signing
is on the roadmap and will close that gap; v1 ships hashes only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ai_bom.discovery import sha256_file
from ai_bom.models import Manifest, canonical_json, sha256_text


@dataclass
class VerifyResult:
    valid: bool
    problems: list[str] = field(default_factory=list)
    checked_files: int = 0


def verify_manifest(manifest: Manifest, root: Path | str | None = None) -> VerifyResult:
    problems: list[str] = []
    checked_files = 0

    if not manifest.digest:
        problems.append("manifest has no digest")
    elif manifest.digest != manifest.compute_digest():
        problems.append(
            "manifest digest mismatch: contents were edited after the digest was computed"
        )

    for comp in manifest.components:
        if comp.digest and comp.digest != comp.compute_digest():
            problems.append(
                f"component digest mismatch for {comp.category}/{comp.name}: "
                "its recorded fields were edited"
            )

    if root is not None:
        root_path = Path(root)
        seen_paths: set[str] = set()
        for comp in manifest.components:
            if comp.path is None or comp.sha256 is None:
                continue
            if comp.category == "mcp_servers":
                # MCP components hash their config entry, not the whole
                # file. The entry check below covers them; the file
                # level check runs once per config file via a sibling
                # component when present, so skip the raw file compare.
                continue
            target = root_path / comp.path
            if comp.path in seen_paths:
                continue
            seen_paths.add(comp.path)
            if not target.is_file():
                problems.append(f"missing file for {comp.category}/{comp.name}: {comp.path}")
                continue
            checked_files += 1
            if comp.size_bytes is not None and target.stat().st_size != comp.size_bytes:
                problems.append(
                    f"size changed for {comp.category}/{comp.name}: {comp.path} "
                    f"was {comp.size_bytes} bytes, now {target.stat().st_size}"
                )
                continue
            if sha256_file(target) != comp.sha256:
                problems.append(
                    f"hash changed for {comp.category}/{comp.name}: {comp.path} "
                    "does not match the recorded SHA-256"
                )
        problems.extend(_verify_mcp_entries(manifest, root_path))
        checked_files += _count_mcp_files(manifest, root_path)

    return VerifyResult(valid=not problems, problems=problems, checked_files=checked_files)


def _mcp_config_files(manifest: Manifest) -> dict[str, list]:
    by_path: dict[str, list] = {}
    for comp in manifest.components:
        if comp.category == "mcp_servers" and comp.path is not None:
            by_path.setdefault(comp.path, []).append(comp)
    return by_path


def _count_mcp_files(manifest: Manifest, root_path: Path) -> int:
    count = 0
    for rel in _mcp_config_files(manifest):
        if (root_path / rel).is_file():
            count += 1
    return count


def _verify_mcp_entries(manifest: Manifest, root_path: Path) -> list[str]:
    problems: list[str] = []
    for rel, comps in _mcp_config_files(manifest).items():
        target = root_path / rel
        if not target.is_file():
            for comp in comps:
                problems.append(f"missing file for mcp_servers/{comp.name}: {rel}")
            continue
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (ValueError, OSError, UnicodeDecodeError):
            problems.append(f"MCP config is no longer readable JSON: {rel}")
            continue
        servers = data.get("mcpServers", {}) if isinstance(data, dict) else {}
        for comp in comps:
            config = servers.get(comp.name) if isinstance(servers, dict) else None
            if config is None:
                problems.append(f"MCP server removed from {rel}: {comp.name}")
                continue
            if isinstance(config, dict) and comp.sha256 is not None:
                actual = sha256_text(canonical_json(config))
                if actual != comp.sha256:
                    problems.append(
                        f"MCP server config changed in {rel}: {comp.name} "
                        "does not match the recorded hash"
                    )
    return problems
