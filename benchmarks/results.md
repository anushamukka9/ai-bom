# Benchmark results

Measured on the build machine (this VM, Linux x86_64, Python 3.12)
with `python benchmarks/bench.py`: median of 5 rounds, 1,000
iterations per round, against the bundled fixture project (13
components: 4 models, 2 tools, 2 MCP servers, 2 datasets, 3
prompts). A second consecutive run measured 633 scans/sec and 2,977
verifies/sec, so treat these as ballpark figures for a small tree,
not promises.

| Benchmark | Result |
|---|---|
| Manifest build (fixture project, 13 components) | 1.48 ms average |
| Scan throughput | 677 scans/sec |
| Verify (manifest plus file hashes) | 2,947 verifies/sec |

## What this measures, and what it does not

A scan is a directory walk, a handful of small file parses, and a
SHA-256 of every prompt and dataset file. On the fixture that is
about a millisecond and a half of work, most of it file IO. Real
projects with large datasets will be bound by hashing those files,
which is the honest cost of knowing they did not change. Verify is
the same story from the other side: digests plus re-hashing, no
parsing of dependency files, so it runs several times faster than a
scan.

The CI smoke test (`python -m ai_bom.benchmark`) uses fewer
iterations and only checks that the fixture inventory still matches
the expected counts and that the path runs, not that these exact
numbers hold.

Safe to reproduce the measurement:

```bash
pip install -e .
python benchmarks/bench.py
```
