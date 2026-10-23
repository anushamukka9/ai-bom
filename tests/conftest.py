"""Shared helpers: build small project trees in a temp directory."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def make_project(tmp_path):
    def _make(files: dict[str, str], name: str = "proj") -> Path:
        root = tmp_path / name
        root.mkdir(parents=True, exist_ok=True)
        for rel, content in files.items():
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        return root

    return _make
