"""Tests for the ai-bom CLI: commands and exit codes."""

import json
from pathlib import Path

import pytest

from ai_bom.cli import EXIT_FINDINGS, EXIT_OK, EXIT_USAGE, main
from ai_bom.fixture import build_fixture_project

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def project(tmp_path):
    return build_fixture_project(tmp_path / "fixture")


@pytest.fixture
def manifest_file(project, tmp_path):
    out = tmp_path / "manifest.json"
    assert main(["scan", str(project), "--output", str(out)]) == EXIT_OK
    return out


def test_scan_to_stdout_is_json(project, capsys):
    assert main(["scan", str(project)]) == EXIT_OK
    data = json.loads(capsys.readouterr().out)
    assert data["project"] == "fixture"
    assert data["digest"]
    assert len(data["components"]) == 13


def test_scan_output_file(project, tmp_path, capsys):
    out = tmp_path / "m.json"
    assert main(["scan", str(project), "-o", str(out)]) == EXIT_OK
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data["components"]) == 13
    assert "13 components" in capsys.readouterr().out


def test_scan_markdown_format(project, capsys):
    assert main(["scan", str(project), "--format", "markdown"]) == EXIT_OK
    text = capsys.readouterr().out
    assert "# AI Bill of Materials" in text
    assert "| models | 4 |" in text
    assert "gpt-4o" in text


def test_scan_missing_path_is_usage_error(tmp_path):
    assert main(["scan", str(tmp_path / "nope")]) == EXIT_USAGE


def test_scan_file_path_is_usage_error(tmp_path):
    a_file = tmp_path / "f.txt"
    a_file.write_text("x", encoding="utf-8")
    assert main(["scan", str(a_file)]) == EXIT_USAGE


def test_show_prints_summary(manifest_file, capsys):
    assert main(["show", str(manifest_file)]) == EXIT_OK
    text = capsys.readouterr().out
    assert "components: 13 total" in text
    assert "digest:" in text
    assert "gpt-4o" in text


def test_show_missing_manifest_is_usage_error(tmp_path):
    assert main(["show", str(tmp_path / "nope.json")]) == EXIT_USAGE


def test_show_unparsable_manifest_is_usage_error(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("this is not json", encoding="utf-8")
    assert main(["show", str(bad)]) == EXIT_USAGE


def test_verify_ok_with_project(manifest_file, project, capsys):
    assert main(["verify", str(manifest_file), str(project)]) == EXIT_OK
    assert "verify ok" in capsys.readouterr().out


def test_verify_ok_internal_only(manifest_file):
    assert main(["verify", str(manifest_file)]) == EXIT_OK


def test_verify_tampered_file_exits_1(manifest_file, project):
    target = project / "prompts" / "system.prompt"
    target.write_text("changed after the scan\n", encoding="utf-8")
    assert main(["verify", str(manifest_file), str(project)]) == EXIT_FINDINGS


def test_verify_edited_manifest_exits_1(manifest_file, tmp_path):
    data = json.loads(manifest_file.read_text(encoding="utf-8"))
    data["components"][0]["name"] = "tampered"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(data), encoding="utf-8")
    assert main(["verify", str(bad)]) == EXIT_FINDINGS


def test_verify_missing_manifest_is_usage_error(tmp_path):
    assert main(["verify", str(tmp_path / "nope.json")]) == EXIT_USAGE


def test_verify_bad_project_path_is_usage_error(manifest_file, tmp_path):
    assert main(["verify", str(manifest_file), str(tmp_path / "nope")]) == EXIT_USAGE


def test_diff_identical_exits_0(manifest_file):
    assert main(["diff", str(manifest_file), str(manifest_file)]) == EXIT_OK


def test_diff_with_changes_exits_1(manifest_file, project, tmp_path, capsys):
    target = project / "data" / "tickets.csv"
    target.write_text("id,status,subject\n7,open,changed\n", encoding="utf-8")
    newer = tmp_path / "newer.json"
    assert main(["scan", str(project), "--output", str(newer)]) == EXIT_OK
    capsys.readouterr()
    assert main(["diff", str(manifest_file), str(newer)]) == EXIT_FINDINGS
    out = capsys.readouterr().out
    assert "changed:" in out
    assert "tickets.csv" in out


def test_diff_json_format(manifest_file, project, tmp_path, capsys):
    (project / "extra.prompt").write_text("new prompt\n", encoding="utf-8")
    newer = tmp_path / "newer.json"
    assert main(["scan", str(project), "--output", str(newer)]) == EXIT_OK
    capsys.readouterr()
    assert main(["diff", str(manifest_file), str(newer), "--format", "json"]) == EXIT_FINDINGS
    data = json.loads(capsys.readouterr().out)
    assert [c["name"] for c in data["added"]] == ["extra.prompt"]


def test_diff_missing_file_is_usage_error(manifest_file, tmp_path):
    assert main(["diff", str(manifest_file), str(tmp_path / "nope.json")]) == EXIT_USAGE


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert "0.2.0" in capsys.readouterr().out


def test_scan_example_project_via_cli(capsys):
    example = ROOT / "examples" / "example_project"
    assert main(["scan", str(example)]) == EXIT_OK
    data = json.loads(capsys.readouterr().out)
    assert len(data["components"]) == 13
