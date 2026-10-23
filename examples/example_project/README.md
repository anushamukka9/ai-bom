# Example project

A tiny fake support agent, kept here so the quickstart and the tests
have a real tree to scan. Nothing in this directory runs. It exists
to be inventoried.

What a scan should find here (13 components):

| Category | Components | Found from |
|---|---|---|
| models | gpt-4o | declared in `aibom.json` |
| models | openai, anthropic | `requirements.txt` |
| models | cohere | imported in `src/app.py` |
| tools | ticket-lookup | declared in `aibom.json` |
| tools | langchain | `requirements.txt` |
| mcp_servers | filesystem, ticket-db | `mcpServers` in `mcp.json` |
| datasets | tickets.csv, faq.jsonl | files under `data/` |
| prompts | system.prompt, summary.jinja | files under `prompts/` |
| prompts | email.j2 | a `.j2` template under `templates/` |

Try it:

```bash
ai-bom scan examples/example_project
```
