"""Tests for the manifest data model and its digests."""

import json

import pytest

from ai_bom.models import (
    CATEGORIES,
    Component,
    Manifest,
    canonical_json,
    sha256_text,
)


def _comp(**kwargs) -> Component:
    base = {"name": "gpt-4o", "category": "models", "source": "aibom.json"}
    base.update(kwargs)
    return Component(**base)


def test_component_digest_is_computed():
    comp = _comp()
    assert comp.digest == comp.compute_digest()
    assert len(comp.digest) == 64


def test_component_digest_changes_with_fields():
    assert _comp().digest != _comp(version="2").digest
    assert _comp().digest != _comp(sha256="ab" * 32).digest
    assert _comp().digest != _comp(source="other.json").digest


def test_component_rejects_unknown_category():
    with pytest.raises(ValueError):
        Component(name="x", category="widgets", source="s")


def test_component_key_includes_name_and_path():
    a = Component(name="srv", category="mcp_servers", source="mcp.json", path="mcp.json")
    b = Component(name="db", category="mcp_servers", source="mcp.json", path="mcp.json")
    assert a.key() != b.key()


def test_component_round_trip():
    comp = _comp(version="2024-08-06", path="data/x.csv", size_bytes=12, sha256="cd" * 32)
    assert Component.from_dict(comp.to_dict()).to_dict() == comp.to_dict()


def test_canonical_json_sorts_keys():
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_sha256_text_known_value():
    assert sha256_text("") == ("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")


def _manifest(**kwargs) -> Manifest:
    base = {
        "project": "demo",
        "components": [_comp(), _comp(name="langchain", category="tools")],
        "generated_at": "2026-01-01T00:00:00Z",
        "generator": "ai-bom 0.1.0",
    }
    base.update(kwargs)
    manifest = Manifest(**base)
    manifest.refresh_digest()
    return manifest


def test_manifest_counts_cover_all_categories():
    counts = _manifest().counts()
    assert set(counts) == set(CATEGORIES)
    assert counts["models"] == 1
    assert counts["tools"] == 1
    assert counts["datasets"] == 0


def test_manifest_round_trip_equality():
    manifest = _manifest()
    assert Manifest.from_json(manifest.to_json()) == manifest


def test_manifest_digest_ignores_generated_at():
    early = _manifest(generated_at="2026-01-01T00:00:00Z")
    late = _manifest(generated_at="2027-06-06T06:06:06Z")
    assert early.digest == late.digest


def test_manifest_digest_changes_with_components():
    one = _manifest()
    two = _manifest(components=[_comp()])
    assert one.digest != two.digest


def test_manifest_sorted_components_follow_category_order():
    manifest = Manifest(
        project="demo",
        components=[
            _comp(name="p", category="prompts"),
            _comp(name="m", category="models"),
            _comp(name="d", category="datasets"),
        ],
    )
    order = [comp.category for comp in manifest.sorted_components()]
    assert order == ["models", "datasets", "prompts"]


def test_from_json_rejects_non_object():
    with pytest.raises(ValueError):
        Manifest.from_json('["not", "an", "object"]')


def test_from_dict_rejects_non_list_components():
    with pytest.raises(ValueError):
        Manifest.from_dict({"project": "x", "components": {"nope": 1}})


def test_to_json_is_valid_json_with_digest():
    data = json.loads(_manifest().to_json())
    assert data["schema_version"] == "1.0"
    assert data["digest"]
    assert len(data["components"]) == 2
