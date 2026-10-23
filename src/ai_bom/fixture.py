"""A small example agent project, written to disk on demand.

The benchmark and the tests both need a project with known contents.
This module writes the same project that lives in
``examples/example_project/`` so the measured numbers and the test
expectations describe the same thing. If you change one, change the
other; a test scans both and expects identical counts.

Expected inventory: 4 models, 2 tools, 2 MCP servers, 2 datasets,
3 prompts. 13 components in total.
"""

from __future__ import annotations

from pathlib import Path

EXPECTED_COUNTS = {
    "models": 4,
    "tools": 2,
    "mcp_servers": 2,
    "datasets": 2,
    "prompts": 3,
}

FIXTURE_FILES: dict[str, str] = {
    "requirements.txt": ("openai==1.40.0\nanthropic>=0.34.0\nlangchain==0.2.14\nrequests>=2.32\n"),
    "aibom.json": (
        "{\n"
        '  "models": [{"name": "gpt-4o", "version": "2024-08-06"}],\n'
        '  "tools": [{"name": "ticket-lookup", "version": "2.1.0"}]\n'
        "}\n"
    ),
    "mcp.json": (
        "{\n"
        '  "mcpServers": {\n'
        '    "filesystem": {\n'
        '      "command": "npx",\n'
        '      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]\n'
        "    },\n"
        '    "ticket-db": {\n'
        '      "command": "python",\n'
        '      "args": ["-m", "ticket_db_mcp"]\n'
        "    }\n"
        "  }\n"
        "}\n"
    ),
    "prompts/system.prompt": (
        "You are a support agent for a small software company.\n"
        "Answer from the ticket history and the FAQ. If you do not\n"
        "know, say so and offer to open a ticket.\n"
    ),
    "prompts/summary.jinja": ("Summarize this ticket thread in three lines.\n\n{{ thread }}\n"),
    "templates/email.j2": ("Hi {{ customer_name }},\n\nThanks for reaching out. {{ body }}\n"),
    "data/tickets.csv": "id,status,subject\n1,open,login fails\n2,closed,export is slow\n",
    "data/faq.jsonl": (
        '{"q": "how do I reset my password", "a": "use the reset link"}\n'
        '{"q": "where is my invoice", "a": "billing page, top right"}\n'
    ),
    "src/app.py": (
        '"""Example agent app. Fixture only; nothing here runs."""\n\n'
        "import cohere\n"
        "import openai\n\n"
        "client = openai.OpenAI()\n"
        "backup = cohere.Client()\n"
    ),
}


def build_fixture_project(root: Path) -> Path:
    """Write the fixture project under ``root`` and return ``root``."""
    root.mkdir(parents=True, exist_ok=True)
    for rel, content in FIXTURE_FILES.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root
