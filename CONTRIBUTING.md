# Contributing to ai-bom

Thanks for considering a contribution. This is a small, focused tool
and we want to keep it that way.

## What fits here

- New discovery sources with fixture tests: show the project shape
  that must be found alongside the near-miss that must not be.
- Entries for the known-package table, with a note on why the package
  belongs in its category.
- Docs, examples, and benchmark additions.

## What does not fit

- Runtime tracing, network calls, or anything that executes the
  scanned project. Discovery is static on purpose.
- Dependencies in the core. It is stdlib-only and it should stay
  that way.
- Guessing. A signal that is not in the tree does not go in the
  manifest. If a component cannot be found statically, the answer is
  a declaration file entry, not a heuristic.

## How to contribute

1. Fork the repo and create a branch: `git checkout -b fix/short-desc`.
2. Add your change plus tests. Discovery work needs fixture tests:
   the shape that must be inventoried alongside the shape that must
   be left out.
3. Run the gates: `pytest` and `ruff check` / `ruff format --check`.
   Both must be clean.
4. Write your feature's limitations honestly. Every part of this
   tool documents what it cannot do. That is a requirement, not a
   suggestion.
5. Open a PR with a short description: what it does, why, and the
   test evidence. Keep the human voice: plain sentences, no hype.

## A note on example secrets

GitHub's secret scanner blocks pushes containing real provider key
formats, even obviously fake ones. If a test fixture or example needs
a secret-shaped value, keep it clearly fake and never in a real
provider's exact format. Env files in fixtures should carry model
names only, never key material. Do not disable push protection to
land a fixture.

## Style

- Python 3.10+, `src/` layout, type hints on public APIs.
- Line length 100, ruff-enforced.
- No em-dashes anywhere. This is a hard rule for this repo.
- Commit messages in imperative mood: `fix: hash MCP entries per server`,
  not `fixed MCP entry hashing`.
