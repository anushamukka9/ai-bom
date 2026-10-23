"""Diff two manifests: what was added, removed, or changed.

Components are matched by identity: category, name, and path. A
matched pair counts as changed when its version, hash, size, or
source differs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ai_bom.models import Component, Manifest

_CHANGED_FIELDS = ("version", "sha256", "size_bytes", "source")


@dataclass
class ComponentChange:
    key: tuple[str, str, str]
    before: Component
    after: Component
    fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "category": self.key[0],
            "name": self.after.name,
            "fields": list(self.fields),
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
        }


@dataclass
class Diff:
    added: list[Component] = field(default_factory=list)
    removed: list[Component] = field(default_factory=list)
    changed: list[ComponentChange] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.changed)

    def to_dict(self) -> dict[str, object]:
        return {
            "added": [comp.to_dict() for comp in self.added],
            "removed": [comp.to_dict() for comp in self.removed],
            "changed": [change.to_dict() for change in self.changed],
        }


def diff_manifests(old: Manifest, new: Manifest) -> Diff:
    old_by_key = {comp.key(): comp for comp in old.components}
    new_by_key = {comp.key(): comp for comp in new.components}
    diff = Diff()
    for key in sorted(new_by_key.keys() - old_by_key.keys()):
        diff.added.append(new_by_key[key])
    for key in sorted(old_by_key.keys() - new_by_key.keys()):
        diff.removed.append(old_by_key[key])
    for key in sorted(old_by_key.keys() & new_by_key.keys()):
        before = old_by_key[key]
        after = new_by_key[key]
        fields = [name for name in _CHANGED_FIELDS if getattr(before, name) != getattr(after, name)]
        if before.name != after.name:
            fields.append("name")
        if fields:
            diff.changed.append(ComponentChange(key=key, before=before, after=after, fields=fields))
    return diff
