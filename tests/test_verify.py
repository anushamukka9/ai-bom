"""Tests for verification: tamper with files and manifests, get caught."""

import json

from ai_bom import scan_project, verify_manifest
from ai_bom.fixture import build_fixture_project
from ai_bom.models import Manifest

TS = "2026-01-01T00:00:00Z"


def _fixture(tmp_path):
    project = build_fixture_project(tmp_path / "fixture")
    return project, scan_project(project, generated_at=TS)


def test_fresh_manifest_verifies_with_root(tmp_path):
    project, manifest = _fixture(tmp_path)
    result = verify_manifest(manifest, project)
    assert result.valid
    assert result.problems == []
    assert result.checked_files >= 5


def test_fresh_manifest_verifies_internal_only(tmp_path):
    _, manifest = _fixture(tmp_path)
    result = verify_manifest(manifest)
    assert result.valid
    assert result.checked_files == 0


def test_edited_prompt_file_fails(tmp_path):
    project, manifest = _fixture(tmp_path)
    target = project / "prompts" / "system.prompt"
    target.write_text(target.read_text(encoding="utf-8") + "extra line\n", encoding="utf-8")
    result = verify_manifest(manifest, project)
    assert not result.valid
    assert any("system.prompt" in problem for problem in result.problems)


def test_edited_dataset_fails(tmp_path):
    project, manifest = _fixture(tmp_path)
    target = project / "data" / "tickets.csv"
    target.write_text("id,status,subject\n9,open,sneaky\n", encoding="utf-8")
    result = verify_manifest(manifest, project)
    assert not result.valid
    assert any("tickets.csv" in problem for problem in result.problems)


def test_deleted_file_fails(tmp_path):
    project, manifest = _fixture(tmp_path)
    (project / "data" / "faq.jsonl").unlink()
    result = verify_manifest(manifest, project)
    assert not result.valid
    assert any("missing" in problem for problem in result.problems)


def test_internal_only_verify_misses_file_edits(tmp_path):
    project, manifest = _fixture(tmp_path)
    target = project / "prompts" / "system.prompt"
    target.write_text("rewritten entirely\n", encoding="utf-8")
    assert verify_manifest(manifest).valid
    assert not verify_manifest(manifest, project).valid


def test_edited_component_name_in_manifest_fails(tmp_path):
    _, manifest = _fixture(tmp_path)
    data = json.loads(manifest.to_json())
    data["components"][0]["name"] = "tampered-name"
    bad = Manifest.from_json(json.dumps(data))
    result = verify_manifest(bad)
    assert not result.valid
    assert any("digest mismatch" in problem for problem in result.problems)


def test_edited_component_version_in_manifest_fails(tmp_path):
    _, manifest = _fixture(tmp_path)
    data = json.loads(manifest.to_json())
    for comp in data["components"]:
        if comp["name"] == "gpt-4o":
            comp["version"] = "9999-99-99"
    bad = Manifest.from_json(json.dumps(data))
    assert not verify_manifest(bad).valid


def test_replaced_manifest_digest_fails(tmp_path):
    _, manifest = _fixture(tmp_path)
    data = json.loads(manifest.to_json())
    data["digest"] = "0" * 64
    bad = Manifest.from_json(json.dumps(data))
    result = verify_manifest(bad)
    assert not result.valid
    assert any("manifest digest mismatch" in problem for problem in result.problems)


def test_replaced_component_digest_fails(tmp_path):
    _, manifest = _fixture(tmp_path)
    data = json.loads(manifest.to_json())
    data["components"][0]["digest"] = "f" * 64
    bad = Manifest.from_json(json.dumps(data))
    assert not verify_manifest(bad).valid


def test_missing_digest_fails(tmp_path):
    _, manifest = _fixture(tmp_path)
    manifest.digest = ""
    result = verify_manifest(manifest)
    assert not result.valid
    assert any("no digest" in problem for problem in result.problems)


def test_edited_generated_at_still_verifies(tmp_path):
    _, manifest = _fixture(tmp_path)
    data = json.loads(manifest.to_json())
    data["generated_at"] = "2030-01-01T00:00:00Z"
    edited = Manifest.from_json(json.dumps(data))
    assert verify_manifest(edited).valid


def test_mcp_entry_edit_fails(tmp_path):
    project, manifest = _fixture(tmp_path)
    config = project / "mcp.json"
    data = json.loads(config.read_text(encoding="utf-8"))
    data["mcpServers"]["filesystem"]["args"] = ["-y", "something-else"]
    config.write_text(json.dumps(data, indent=2), encoding="utf-8")
    result = verify_manifest(manifest, project)
    assert not result.valid
    assert any("filesystem" in problem for problem in result.problems)


def test_mcp_server_removed_fails(tmp_path):
    project, manifest = _fixture(tmp_path)
    config = project / "mcp.json"
    data = json.loads(config.read_text(encoding="utf-8"))
    del data["mcpServers"]["ticket-db"]
    config.write_text(json.dumps(data, indent=2), encoding="utf-8")
    result = verify_manifest(manifest, project)
    assert not result.valid
    assert any("ticket-db" in problem for problem in result.problems)


def test_mcp_neighbour_edit_does_not_flag_untouched_server(tmp_path):
    project, manifest = _fixture(tmp_path)
    config = project / "mcp.json"
    data = json.loads(config.read_text(encoding="utf-8"))
    data["mcpServers"]["ticket-db"]["args"] = ["-m", "other_module"]
    config.write_text(json.dumps(data, indent=2), encoding="utf-8")
    result = verify_manifest(manifest, project)
    assert not result.valid
    assert not any("filesystem" in problem for problem in result.problems)


def test_rescan_after_change_verifies_clean(tmp_path):
    project, manifest = _fixture(tmp_path)
    target = project / "prompts" / "system.prompt"
    target.write_text("new prompt, new manifest\n", encoding="utf-8")
    fresh = scan_project(project, generated_at=TS)
    assert fresh.digest != manifest.digest
    assert verify_manifest(fresh, project).valid
