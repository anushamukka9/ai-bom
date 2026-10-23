# Discovery: what the scanner reads

Discovery is static and conservative. The scanner parses declared
sources in a fixed order, and the first source to name a component
wins, so attribution in the manifest is stable from run to run. If a
signal is not in the tree, the component is not in the manifest.

## 1. Declaration files

`aibom.json`, `ai-bom.json`, or `ai-bom.toml` at the project root.
Use these for parts no file gives away, like a hosted model reached
over HTTP, or a dataset mounted at runtime.

```json
{
  "models": [{"name": "gpt-4o", "version": "2024-08-06"}],
  "tools": [{"name": "ticket-lookup", "version": "2.1.0"}],
  "datasets": [{"name": "support-faq", "path": "data/faq.jsonl"}]
}
```

An entry may carry a `path` relative to the project root. When the
file exists, the scanner records its size and SHA-256 like any other
file-backed component. Any of the five categories may be declared:
`models`, `tools`, `mcp_servers`, `datasets`, `prompts`.

The TOML form uses the same shape as array-of-tables:

```toml
[[models]]
name = "gpt-4o"
version = "2024-08-06"
```

On Python 3.11 and later the TOML file is parsed with the standard
library. On 3.10 a small built-in parser handles the subset above.

## 2. MCP client configs

Any `.json` file in the tree whose top level holds an `mcpServers`
object: Claude Desktop style configs, Cursor style configs, or a
plain `mcp.json`. Each server becomes one `mcp_servers` component.
Its recorded hash covers that server's own config entry, so editing
one server's command or args is detected without flagging edits to
its neighbours.

## 3. Dependencies

`requirements.txt` files and the root `pyproject.toml` dependency
list, mapped through a known-package table (see
`ai_bom.KNOWN_PACKAGES`). Provider packages like `openai` and
`anthropic` land in `models`, framework packages like `langchain`
land in `tools`, the `mcp` package lands in `mcp_servers`, and the
Hugging Face `datasets` package lands in `datasets`. A pinned
`name==1.2.3` requirement records its version; a range records none,
because a range is not a version. Packages outside the table are
ignored, not guessed at.

## 4. Python imports

`import` and `from` lines in `.py` files, mapped through the same
table by module name (`llama_index` maps to the `llama-index`
package, and so on). An import and a dependency naming the same
package produce one component; the dependency, scanned first, keeps
the attribution.

## 5. Env-style model references

Files named `.env`, `.env.example`, and friends are read for keys
named `MODEL`, `MODEL_NAME`, or ending in `_MODEL` / `_MODEL_NAME`.
The value becomes a `models` component. Nothing else in the file is
read into the manifest, and key material is never recorded. This is
the one place values are taken from a config file, and it is limited
to model names on purpose.

## 6. Prompt files

Files ending in `.prompt`, `.jinja`, `.j2`, or `.jinja2`, plus any
file under a `prompts/` directory. Each file is one component with
its path, size, and SHA-256.

## 7. Dataset files

Any file under a `data/` or `datasets/` directory, plus `.csv`,
`.jsonl`, and `.parquet` files anywhere in the tree. The manifest
records name, path, size, and SHA-256. Contents are hashed, never
parsed or stored.

## What is skipped

`.git`, virtualenvs, `__pycache__`, `node_modules`, `dist`, `build`,
and other dot-directories (except `.cursor`, which holds real MCP
configs) are not walked. Non-UTF-8 files are skipped rather than
crashing the scan.
