"""Tests for the CycloneDX export."""

import json
from pathlib import Path

import pytest

from ai_bom.cli import EXIT_OK, EXIT_USAGE, main
from ai_bom.cyclonedx import manifest_to_cyclonedx_json, to_cyclonedx
from ai_bom.fixture import build_fixture_project
from ai_bom.models import Component, Manifest


@pytest.fixture
def project(tmp_path):
    return build_fixture_project(tmp_path / "fixture")


@pytest.fixture
def manifest(project):
    from ai_bom import scan_project

    return scan_project(project)


def test_bom_header(manifest):
    bom = to_cyclonedx(manifest)
    assert bom["bomFormat"] == "CycloneDX"
    assert bom["specVersion"] == "1.5"
    assert bom["serialNumber"].startswith("urn:uuid:")
    assert bom["version"] == 1


def test_serial_number_is_stable_for_same_digest(manifest):
    assert to_cyclonedx(manifest)["serialNumber"] == to_cyclonedx(manifest)["serialNumber"]


def test_metadata_names_project_and_tool(manifest):
    metadata = to_cyclonedx(manifest)["metadata"]
    assert metadata["component"]["name"] == "fixture"
    assert metadata["component"]["type"] == "application"
    assert metadata["tools"][0]["name"] == "ai-bom"
    props = {p["name"]: p["value"] for p in metadata["properties"]}
    assert props["ai-bom:digest"] == manifest.digest
    assert props["ai-bom:signed"] == "false"


def test_every_component_is_exported(manifest):
    bom = to_cyclonedx(manifest)
    assert len(bom["components"]) == 13
    refs = [c["bom-ref"] for c in bom["components"]]
    assert len(set(refs)) == 13


def test_category_type_mapping(manifest):
    by_name = {c["name"]: c for c in to_cyclonedx(manifest)["components"]}
    assert by_name["gpt-4o"]["type"] == "machine-learning-model"
    assert by_name["filesystem"]["type"] == "application"
    assert by_name["tickets.csv"]["type"] == "data"
    assert by_name["system.prompt"]["type"] == "file"


def test_component_properties_keep_ai_bom_fields(manifest):
    bom = to_cyclonedx(manifest)
    entry = next(c for c in bom["components"] if c["name"] == "tickets.csv")
    props = {p["name"]: p["value"] for p in entry["properties"]}
    assert props["ai-bom:category"] == "datasets"
    assert props["ai-bom:path"] == "data/tickets.csv"
    assert props["ai-bom:digest"]


def test_file_hash_becomes_cyclonedx_hash(manifest):
    bom = to_cyclonedx(manifest)
    entry = next(c for c in bom["components"] if c["name"] == "tickets.csv")
    assert entry["hashes"][0]["alg"] == "SHA-256"
    assert len(entry["hashes"][0]["content"]) == 64


def test_version_carried_when_present():
    manifest = Manifest(
        project="demo",
        components=[Component(name="gpt-4o", category="models", source="x", version="1.0")],
    )
    manifest.refresh_digest()
    entry = to_cyclonedx(manifest)["components"][0]
    assert entry["version"] == "1.0"


def test_json_round_trips_as_json(manifest):
    data = json.loads(manifest_to_cyclonedx_json(manifest))
    assert data["bomFormat"] == "CycloneDX"
    assert len(data["components"]) == 13


def test_empty_manifest_exports_cleanly():
    manifest = Manifest(project="empty", components=[])
    manifest.refresh_digest()
    bom = to_cyclonedx(manifest)
    assert bom["components"] == []
    assert bom["metadata"]["component"]["name"] == "empty"


def test_cli_export_to_stdout(project, tmp_path, capsys):
    manifest_file = tmp_path / "manifest.json"
    assert main(["scan", str(project), "--output", str(manifest_file)]) == EXIT_OK
    capsys.readouterr()
    assert main(["export", str(manifest_file)]) == EXIT_OK
    data = json.loads(capsys.readouterr().out)
    assert data["specVersion"] == "1.5"
    assert len(data["components"]) == 13


def test_cli_export_to_file(project, tmp_path, capsys):
    manifest_file = tmp_path / "manifest.json"
    out = tmp_path / "bom.cdx.json"
    assert main(["scan", str(project), "--output", str(manifest_file)]) == EXIT_OK
    capsys.readouterr()
    assert main(["export", str(manifest_file), "--output", str(out)]) == EXIT_OK
    assert "CycloneDX 1.5, 13 components" in capsys.readouterr().out
    data = json.loads(Path(out).read_text(encoding="utf-8"))
    assert data["bomFormat"] == "CycloneDX"


def test_cli_export_missing_manifest_is_usage_error(tmp_path):
    assert main(["export", str(tmp_path / "nope.json")]) == EXIT_USAGE


def test_cli_scan_cyclonedx_format(project, capsys):
    assert main(["scan", str(project), "--format", "cyclonedx"]) == EXIT_OK
    data = json.loads(capsys.readouterr().out)
    assert data["bomFormat"] == "CycloneDX"
    assert len(data["components"]) == 13
