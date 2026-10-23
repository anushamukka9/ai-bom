"""Tests for manifest diffing."""

from ai_bom import diff_manifests, scan_project
from ai_bom.fixture import build_fixture_project
from ai_bom.models import Component, Manifest

TS = "2026-01-01T00:00:00Z"


def _manifest(*components: Component) -> Manifest:
    manifest = Manifest(project="demo", components=list(components), generated_at=TS)
    manifest.refresh_digest()
    return manifest


def _comp(name="gpt-4o", category="models", **kwargs) -> Component:
    base = {"source": "aibom.json"}
    base.update(kwargs)
    return Component(name=name, category=category, **base)


def test_identical_manifests_have_no_changes(tmp_path):
    project = build_fixture_project(tmp_path / "fixture")
    first = scan_project(project, generated_at=TS)
    second = scan_project(project, generated_at=TS)
    diff = diff_manifests(first, second)
    assert not diff.has_changes
    assert diff.added == [] and diff.removed == [] and diff.changed == []


def test_added_component():
    diff = diff_manifests(_manifest(_comp()), _manifest(_comp(), _comp(name="cohere")))
    assert [c.name for c in diff.added] == ["cohere"]
    assert diff.has_changes


def test_removed_component():
    diff = diff_manifests(_manifest(_comp(), _comp(name="cohere")), _manifest(_comp()))
    assert [c.name for c in diff.removed] == ["cohere"]


def test_changed_version():
    diff = diff_manifests(_manifest(_comp(version="1")), _manifest(_comp(version="2")))
    assert len(diff.changed) == 1
    assert diff.changed[0].fields == ["version"]
    assert diff.changed[0].before.version == "1"
    assert diff.changed[0].after.version == "2"


def test_changed_hash(tmp_path):
    project = build_fixture_project(tmp_path / "fixture")
    before = scan_project(project, generated_at=TS)
    target = project / "data" / "tickets.csv"
    target.write_text("id,status,subject\n3,open,new row\n", encoding="utf-8")
    after = scan_project(project, generated_at=TS)
    diff = diff_manifests(before, after)
    assert len(diff.changed) == 1
    assert diff.changed[0].after.name == "tickets.csv"
    assert "sha256" in diff.changed[0].fields


def test_renamed_file_is_add_plus_remove(tmp_path):
    project = build_fixture_project(tmp_path / "fixture")
    before = scan_project(project, generated_at=TS)
    (project / "data" / "tickets.csv").rename(project / "data" / "renamed.csv")
    after = scan_project(project, generated_at=TS)
    diff = diff_manifests(before, after)
    assert [c.name for c in diff.added] == ["renamed.csv"]
    assert [c.name for c in diff.removed] == ["tickets.csv"]


def test_diff_to_dict_shape():
    diff = diff_manifests(_manifest(_comp()), _manifest(_comp(), _comp(name="cohere")))
    data = diff.to_dict()
    assert set(data) == {"added", "removed", "changed"}
    assert data["added"][0]["name"] == "cohere"


def test_empty_diff_has_changes_is_false():
    diff = diff_manifests(_manifest(), _manifest())
    assert not diff.has_changes
