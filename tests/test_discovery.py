"""Tests for static discovery, one source at a time plus the fixture."""

import hashlib
from pathlib import Path

from ai_bom import scan_project
from ai_bom.fixture import EXPECTED_COUNTS, build_fixture_project

ROOT = Path(__file__).resolve().parent.parent
TS = "2026-01-01T00:00:00Z"


def _by_name(manifest):
    return {(c.category, c.name): c for c in manifest.components}


def test_fixture_project_counts(tmp_path):
    project = build_fixture_project(tmp_path / "fixture")
    manifest = scan_project(project, generated_at=TS)
    assert manifest.counts() == EXPECTED_COUNTS
    assert len(manifest.components) == 13


def test_example_project_counts():
    manifest = scan_project(ROOT / "examples" / "example_project", generated_at=TS)
    assert manifest.counts() == EXPECTED_COUNTS


def test_declaration_json_models_and_tools(make_project):
    project = make_project(
        {
            "aibom.json": (
                '{"models": [{"name": "hosted-llm", "version": "7"}],'
                ' "tools": [{"name": "crm-lookup", "version": "1.0"}]}'
            )
        }
    )
    found = _by_name(scan_project(project, generated_at=TS))
    assert found[("models", "hosted-llm")].version == "7"
    assert found[("models", "hosted-llm")].source == "aibom.json"
    assert found[("tools", "crm-lookup")].version == "1.0"


def test_declaration_toml(make_project):
    project = make_project({"ai-bom.toml": '[[models]]\nname = "toml-model"\nversion = "3"\n'})
    found = _by_name(scan_project(project, generated_at=TS))
    assert found[("models", "toml-model")].version == "3"


def test_declaration_with_path_hashes_the_file(make_project):
    project = make_project(
        {
            "aibom.json": '{"datasets": [{"name": "faq", "path": "data/faq.jsonl"}]}',
            "data/faq.jsonl": '{"q": "a"}\n',
        }
    )
    manifest = scan_project(project, generated_at=TS)
    declared = [c for c in manifest.components if c.name == "faq"]
    assert len(declared) == 1
    assert declared[0].sha256 is not None
    assert declared[0].size_bytes == len('{"q": "a"}\n')


def test_declaration_ignores_entries_without_names(make_project):
    project = make_project({"aibom.json": '{"models": [{"version": "1"}, "junk"]}'})
    manifest = scan_project(project, generated_at=TS)
    assert manifest.counts()["models"] == 0


def test_mcp_config_servers_found(make_project):
    project = make_project(
        {
            "mcp.json": (
                '{"mcpServers": {"files": {"command": "npx"},'
                ' "db": {"command": "python", "version": "2"}}}'
            )
        }
    )
    manifest = scan_project(project, generated_at=TS)
    found = _by_name(manifest)
    assert manifest.counts()["mcp_servers"] == 2
    assert found[("mcp_servers", "db")].version == "2"
    assert found[("mcp_servers", "files")].sha256 is not None


def test_mcp_config_in_cursor_dir_found(make_project):
    project = make_project({".cursor/mcp.json": '{"mcpServers": {"srv": {"command": "x"}}}'})
    manifest = scan_project(project, generated_at=TS)
    assert manifest.counts()["mcp_servers"] == 1


def test_json_without_mcp_servers_is_ignored(make_project):
    project = make_project({"config.json": '{"mcpServers": "not-a-dict", "other": 1}'})
    manifest = scan_project(project, generated_at=TS)
    assert manifest.counts()["mcp_servers"] == 0


def test_requirements_pinned_version_recorded(make_project):
    project = make_project({"requirements.txt": "openai==1.40.0\n"})
    found = _by_name(scan_project(project, generated_at=TS))
    assert found[("models", "openai")].version == "1.40.0"
    assert found[("models", "openai")].source == "requirements.txt"


def test_requirements_range_records_no_version(make_project):
    project = make_project({"requirements.txt": "anthropic>=0.34.0\n"})
    found = _by_name(scan_project(project, generated_at=TS))
    assert found[("models", "anthropic")].version is None


def test_requirements_unknown_package_ignored(make_project):
    project = make_project({"requirements.txt": "requests>=2.32\nflask==3.0\n"})
    manifest = scan_project(project, generated_at=TS)
    assert manifest.components == []


def test_requirements_extras_and_env_markers(make_project):
    project = make_project({"requirements.txt": "langchain[openai]==0.2.0; python_version>'3.9'\n"})
    found = _by_name(scan_project(project, generated_at=TS))
    assert found[("tools", "langchain")].version == "0.2.0"


def test_pyproject_dependencies_found(make_project):
    project = make_project(
        {
            "pyproject.toml": (
                '[project]\nname = "demo"\nversion = "0.1.0"\n'
                'dependencies = ["cohere==5.0.0", "requests"]\n'
            )
        }
    )
    found = _by_name(scan_project(project, generated_at=TS))
    assert found[("models", "cohere")].version == "5.0.0"
    assert found[("models", "cohere")].source == "pyproject.toml"


def test_import_only_package_found(make_project):
    project = make_project({"app.py": "import groq\n\nclient = groq.Groq()\n"})
    found = _by_name(scan_project(project, generated_at=TS))
    assert ("models", "groq") in found


def test_import_dedupes_with_dependency_and_dep_wins(make_project):
    project = make_project({"requirements.txt": "openai==1.0.0\n", "app.py": "import openai\n"})
    manifest = scan_project(project, generated_at=TS)
    matches = [c for c in manifest.components if c.name == "openai"]
    assert len(matches) == 1
    assert matches[0].source == "requirements.txt"
    assert matches[0].version == "1.0.0"


def test_from_import_and_dotted_import_mapped(make_project):
    project = make_project(
        {"app.py": "from llama_index.core import Settings\nimport langchain_core.tools\n"}
    )
    found = _by_name(scan_project(project, generated_at=TS))
    assert ("tools", "llama-index") in found
    assert ("tools", "langchain") in found


def test_unmapped_imports_ignored(make_project):
    project = make_project({"app.py": "import json\nimport os\nfrom pathlib import Path\n"})
    manifest = scan_project(project, generated_at=TS)
    assert manifest.components == []


def test_env_model_recorded_and_key_material_never_recorded(make_project):
    project = make_project(
        {".env.example": "OPENAI_MODEL=gpt-4o-mini\nSOME_API_KEY=fake-test-value\n"}
    )
    manifest = scan_project(project, generated_at=TS)
    found = _by_name(manifest)
    assert ("models", "gpt-4o-mini") in found
    assert "fake-test-value" not in manifest.to_json()


def test_env_plain_model_key(make_project):
    project = make_project({".env": "MODEL=llama-3.1-70b\nOTHER=1\n"})
    found = _by_name(scan_project(project, generated_at=TS))
    assert ("models", "llama-3.1-70b") in found


def test_prompt_extensions_found_anywhere(make_project):
    project = make_project(
        {
            "a.prompt": "hi",
            "b.jinja": "{{ x }}",
            "c.j2": "{{ y }}",
            "d.jinja2": "{{ z }}",
            "e.txt": "not a prompt",
        }
    )
    manifest = scan_project(project, generated_at=TS)
    assert manifest.counts()["prompts"] == 4


def test_prompts_directory_any_extension(make_project):
    project = make_project({"prompts/notes.txt": "remember the tone", "prompts/x.md": "# p"})
    manifest = scan_project(project, generated_at=TS)
    assert manifest.counts()["prompts"] == 2


def test_same_prompt_filename_in_two_dirs_both_counted(make_project):
    project = make_project({"prompts/same.prompt": "one", "templates/same.prompt": "two"})
    manifest = scan_project(project, generated_at=TS)
    assert manifest.counts()["prompts"] == 2


def test_dataset_in_data_dir_any_extension(make_project):
    project = make_project({"data/blob.bin": "0101", "datasets/notes.txt": "labels"})
    manifest = scan_project(project, generated_at=TS)
    assert manifest.counts()["datasets"] == 2


def test_dataset_by_extension_outside_data_dir(make_project):
    project = make_project({"exports/report.csv": "a,b\n1,2\n", "root.jsonl": "{}\n"})
    manifest = scan_project(project, generated_at=TS)
    assert manifest.counts()["datasets"] == 2


def test_dataset_contents_never_in_manifest(make_project):
    marker = "MARKER-ROW-CONTENT-12345"
    project = make_project({"data/x.csv": f"id,note\n1,{marker}\n"})
    manifest = scan_project(project, generated_at=TS)
    assert marker not in manifest.to_json()


def test_file_hash_and_size_are_correct(make_project):
    content = "id,status\n1,open\n"
    project = make_project({"data/tickets.csv": content})
    manifest = scan_project(project, generated_at=TS)
    comp = manifest.components[0]
    assert comp.sha256 == hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert comp.size_bytes == len(content.encode("utf-8"))
    assert comp.path == "data/tickets.csv"


def test_skipped_directories_are_not_walked(make_project):
    project = make_project(
        {
            ".venv/lib/hidden.prompt": "nope",
            "__pycache__/cached.prompt": "nope",
            "node_modules/pkg/x.j2": "nope",
            "real.prompt": "yes",
        }
    )
    manifest = scan_project(project, generated_at=TS)
    assert manifest.counts()["prompts"] == 1


def test_scan_is_deterministic(make_project):
    project = build_fixture_project(make_project({}, name="ignored") / "fx")
    first = scan_project(project, generated_at=TS)
    second = scan_project(project, generated_at=TS)
    assert first.digest == second.digest
    assert first.to_json() == second.to_json()


def test_empty_project_scans_clean(make_project):
    project = make_project({"README.md": "# nothing here\n"})
    manifest = scan_project(project, generated_at=TS)
    assert manifest.counts() == {name: 0 for name in manifest.counts()}
    assert manifest.digest


def test_scan_missing_directory_raises(tmp_path):
    import pytest

    with pytest.raises(NotADirectoryError):
        scan_project(tmp_path / "does-not-exist", generated_at=TS)
