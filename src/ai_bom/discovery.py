"""Static discovery: scan a project directory and build a manifest.

Discovery is deliberately conservative. It parses declared sources
(declaration files, dependency lists, MCP client configs, prompt and
dataset files on disk) instead of guessing what an app might use at
runtime. If a signal is not in the tree, it is not in the manifest.

Sources, in scan order (the first source to name a component wins, so
attribution is stable):

1. Declaration files at the project root: ``aibom.json``,
   ``ai-bom.json``, or ``ai-bom.toml``.
2. MCP client configs: any JSON file with an ``mcpServers`` object.
3. Dependencies: ``requirements.txt`` files and ``pyproject.toml``
   dependencies, mapped through a small known-package table.
4. Python imports in ``.py`` files, mapped through the same table.
5. Env-style model references: ``MODEL`` / ``*_MODEL`` keys in
   ``.env`` style files. Only the model name is recorded, never any
   other value from the file.
6. Prompt files: ``*.prompt``, ``*.jinja``, ``*.j2``, ``*.jinja2``,
   and anything under a ``prompts/`` directory.
7. Dataset files: anything under ``data/`` or ``datasets/``, plus
   ``*.csv``, ``*.jsonl``, and ``*.parquet`` files anywhere. Only
   name, path, size, and hash are recorded. Contents are never read
   into the manifest beyond hashing.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from ai_bom.models import (
    CATEGORIES,
    Component,
    Manifest,
    canonical_json,
    sha256_text,
    utc_now_iso,
)

# Package name (normalized) -> (category, display name).
KNOWN_PACKAGES: dict[str, tuple[str, str]] = {
    "openai": ("models", "openai"),
    "anthropic": ("models", "anthropic"),
    "cohere": ("models", "cohere"),
    "mistralai": ("models", "mistralai"),
    "google-generativeai": ("models", "google-generativeai"),
    "google-genai": ("models", "google-genai"),
    "groq": ("models", "groq"),
    "ollama": ("models", "ollama"),
    "replicate": ("models", "replicate"),
    "together": ("models", "together"),
    "fireworks-ai": ("models", "fireworks-ai"),
    "huggingface-hub": ("models", "huggingface-hub"),
    "transformers": ("models", "transformers"),
    "sentence-transformers": ("models", "sentence-transformers"),
    "vllm": ("models", "vllm"),
    "llama-cpp-python": ("models", "llama-cpp-python"),
    "langchain": ("tools", "langchain"),
    "langgraph": ("tools", "langgraph"),
    "llama-index": ("tools", "llama-index"),
    "crewai": ("tools", "crewai"),
    "pyautogen": ("tools", "pyautogen"),
    "semantic-kernel": ("tools", "semantic-kernel"),
    "haystack-ai": ("tools", "haystack-ai"),
    "smolagents": ("tools", "smolagents"),
    "pydantic-ai": ("tools", "pydantic-ai"),
    "dspy": ("tools", "dspy"),
    "mcp": ("mcp_servers", "mcp"),
    "fastmcp": ("mcp_servers", "fastmcp"),
    "datasets": ("datasets", "datasets"),
}

# Importable module name -> package name in KNOWN_PACKAGES.
IMPORT_MAP: dict[str, str] = {
    "openai": "openai",
    "anthropic": "anthropic",
    "cohere": "cohere",
    "mistralai": "mistralai",
    "langchain": "langchain",
    "langchain_core": "langchain",
    "langchain_community": "langchain",
    "langgraph": "langgraph",
    "llama_index": "llama-index",
    "crewai": "crewai",
    "autogen": "pyautogen",
    "semantic_kernel": "semantic-kernel",
    "haystack": "haystack-ai",
    "smolagents": "smolagents",
    "pydantic_ai": "pydantic-ai",
    "dspy": "dspy",
    "mcp": "mcp",
    "fastmcp": "fastmcp",
    "datasets": "datasets",
    "transformers": "transformers",
    "sentence_transformers": "sentence-transformers",
    "huggingface_hub": "huggingface-hub",
    "groq": "groq",
    "ollama": "ollama",
    "replicate": "replicate",
    "together": "together",
    "vllm": "vllm",
}

_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".ruff_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".mypy_cache",
    ".tox",
}

_ALLOWED_DOT_DIRS = {".cursor"}

_PROMPT_SUFFIXES = {".prompt", ".jinja", ".j2", ".jinja2"}
_DATASET_SUFFIXES = {".csv", ".jsonl", ".parquet"}
_IMPORT_RE = re.compile(r"^\s*(?:import|from)\s+([A-Za-z_][\w.]*)", re.MULTILINE)
_MODEL_ENV_RE = re.compile(r"^(?:[A-Z][A-Z0-9_]*_)?MODEL(?:_NAME)?\s*=\s*(.+)$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_package(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def _walk_files(root: Path) -> list[Path]:
    found: list[Path] = []
    for dirpath, filenames in _walk(root):
        for filename in filenames:
            found.append(dirpath / filename)
    return sorted(found)


def _walk(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        kept = []
        for dirname in dirnames:
            if dirname in _SKIP_DIRS or dirname.endswith(".egg-info"):
                continue
            if dirname.startswith(".") and dirname not in _ALLOWED_DOT_DIRS:
                continue
            kept.append(dirname)
        dirnames[:] = sorted(kept)
        yield Path(dirpath), sorted(filenames)


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


class _Collector:
    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], Component] = {}

    def add(self, comp: Component) -> None:
        self._by_key.setdefault(comp.key(), comp)

    def components(self) -> list[Component]:
        return list(self._by_key.values())


def _parse_simple_toml(text: str) -> dict[str, object]:
    """Parse the small TOML subset used by ai-bom.toml declarations.

    Supports ``[[category]]`` array-of-tables with ``key = "value"``
    lines. Used on Python 3.10, which has no tomllib. Anything outside
    the subset is ignored rather than guessed at.
    """
    result: dict[str, object] = {}
    current: dict[str, object] | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[[") and line.endswith("]]"):
            category = line[2:-2].strip()
            entries = result.setdefault(category, [])
            current = {}
            assert isinstance(entries, list)
            entries.append(current)
            continue
        if "=" in line and current is not None:
            key, _, value = line.partition("=")
            value = value.strip()
            if value.startswith('"') and value.endswith('"') and len(value) >= 2:
                value = value[1:-1]
            current[key.strip()] = value
    return result


def _load_declaration(path: Path) -> dict[str, object]:
    if path.suffix == ".toml":
        try:
            import tomllib
        except ModuleNotFoundError:
            return _parse_simple_toml(path.read_text(encoding="utf-8"))
        with path.open("rb") as handle:
            return tomllib.load(handle)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"declaration file {path.name} must contain a JSON object")
    return data


def _scan_declarations(root: Path, collector: _Collector) -> None:
    for filename in ("aibom.json", "ai-bom.json", "ai-bom.toml"):
        path = root / filename
        if not path.is_file():
            continue
        try:
            data = _load_declaration(path)
        except (ValueError, OSError):
            continue
        for category in CATEGORIES:
            entries = data.get(category)
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict) or not entry.get("name"):
                    continue
                comp_path = entry.get("path")
                sha256 = None
                size = None
                rel = None
                if isinstance(comp_path, str):
                    target = root / comp_path
                    rel = Path(comp_path).as_posix()
                    if target.is_file():
                        sha256 = sha256_file(target)
                        size = target.stat().st_size
                collector.add(
                    Component(
                        name=str(entry["name"]),
                        category=category,
                        source=filename,
                        version=str(entry["version"]) if entry.get("version") else None,
                        path=rel,
                        size_bytes=size,
                        sha256=sha256,
                    )
                )


def _scan_mcp_configs(root: Path, files: list[Path], collector: _Collector) -> None:
    for path in files:
        if path.suffix != ".json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError, UnicodeDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        servers = data.get("mcpServers")
        if not isinstance(servers, dict):
            continue
        rel = _rel(root, path)
        file_hash = sha256_file(path)
        for server_name in sorted(servers):
            config = servers[server_name]
            version = None
            entry_hash = file_hash
            if isinstance(config, dict):
                if config.get("version"):
                    version = str(config["version"])
                entry_hash = sha256_text(canonical_json(config))
            collector.add(
                Component(
                    name=str(server_name),
                    category="mcp_servers",
                    source=rel,
                    version=version,
                    path=rel,
                    size_bytes=path.stat().st_size,
                    sha256=entry_hash,
                )
            )


def _split_requirement(line: str) -> tuple[str, str | None] | None:
    line = line.strip()
    if not line or line.startswith("#") or line.startswith("-"):
        return None
    line = line.split("#", 1)[0].strip()
    line = line.split(";", 1)[0].strip()
    if not line:
        return None
    version = None
    if "==" in line:
        name_part, _, version_part = line.partition("==")
        version = version_part.strip().split()[0] if version_part.strip() else None
        line = name_part
    name = re.split(r"[<>=!~\[ ]", line, maxsplit=1)[0].strip()
    if not name:
        return None
    return name, version


def _add_dependency(collector: _Collector, raw_name: str, version: str | None, source: str) -> None:
    known = KNOWN_PACKAGES.get(_normalize_package(raw_name))
    if known is None:
        return
    category, display = known
    collector.add(Component(name=display, category=category, source=source, version=version))


def _pyproject_dependencies(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    try:
        import tomllib
    except ModuleNotFoundError:
        match = re.search(r"(?ms)^\[project\].*?^dependencies\s*=\s*\[(.*?)\]", text)
        if not match:
            return []
        return re.findall(r'"([^"]+)"', match.group(1))
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    project = data.get("project", {})
    deps = project.get("dependencies", [])
    return [str(dep) for dep in deps] if isinstance(deps, list) else []


def _scan_dependencies(root: Path, files: list[Path], collector: _Collector) -> None:
    for path in files:
        if path.name == "requirements.txt" or (
            path.parent.name == "requirements" and path.suffix == ".txt"
        ):
            rel = _rel(root, path)
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            for line in lines:
                parsed = _split_requirement(line)
                if parsed is not None:
                    _add_dependency(collector, parsed[0], parsed[1], rel)
        elif path.name == "pyproject.toml" and path.parent == root:
            try:
                deps = _pyproject_dependencies(path)
            except (ValueError, OSError, UnicodeDecodeError):
                continue
            for dep in deps:
                parsed = _split_requirement(dep)
                if parsed is not None:
                    _add_dependency(collector, parsed[0], parsed[1], "pyproject.toml")


def _scan_imports(root: Path, files: list[Path], collector: _Collector) -> None:
    for path in files:
        if path.suffix != ".py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = _rel(root, path)
        seen_in_file: set[str] = set()
        for match in _IMPORT_RE.finditer(text):
            module = match.group(1)
            package = IMPORT_MAP.get(module)
            if package is None:
                package = IMPORT_MAP.get(module.split(".", 1)[0])
            if package is None or package in seen_in_file:
                continue
            seen_in_file.add(package)
            known = KNOWN_PACKAGES[package]
            collector.add(Component(name=known[1], category=known[0], source=rel, version=None))


def _scan_env_models(root: Path, files: list[Path], collector: _Collector) -> None:
    for path in files:
        if not path.name.startswith(".env"):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        rel = _rel(root, path)
        for line in lines:
            match = _MODEL_ENV_RE.match(line.strip())
            if not match:
                continue
            value = match.group(1).strip().strip('"').strip("'")
            if not value or "your-" in value or value.startswith("<"):
                continue
            collector.add(Component(name=value, category="models", source=rel, version=None))


def _file_component(root: Path, path: Path, category: str) -> Component:
    rel = _rel(root, path)
    return Component(
        name=path.name,
        category=category,
        source=rel,
        path=rel,
        size_bytes=path.stat().st_size,
        sha256=sha256_file(path),
    )


def _scan_prompt_and_dataset_files(root: Path, files: list[Path], collector: _Collector) -> None:
    for path in files:
        parts = set(path.relative_to(root).parts[:-1])
        suffix = path.suffix.lower()
        if suffix in _PROMPT_SUFFIXES or "prompts" in parts:
            if suffix not in {".pyc"}:
                collector.add(_file_component(root, path, "prompts"))
            continue
        if suffix in _DATASET_SUFFIXES or "data" in parts or "datasets" in parts:
            collector.add(_file_component(root, path, "datasets"))


def scan_project(root: Path | str, generated_at: str | None = None) -> Manifest:
    """Scan ``root`` and return its manifest. Deterministic ordering."""
    from ai_bom import __version__

    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise NotADirectoryError(f"not a directory: {root_path}")
    files = _walk_files(root_path)
    collector = _Collector()
    _scan_declarations(root_path, collector)
    _scan_mcp_configs(root_path, files, collector)
    _scan_dependencies(root_path, files, collector)
    _scan_imports(root_path, files, collector)
    _scan_env_models(root_path, files, collector)
    _scan_prompt_and_dataset_files(root_path, files, collector)
    manifest = Manifest(
        project=root_path.name,
        components=collector.components(),
        generated_at=generated_at if generated_at is not None else utc_now_iso(),
        generator=f"ai-bom {__version__}",
    )
    manifest.refresh_digest()
    return manifest
