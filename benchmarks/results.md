# Benchmark results

Measured on the build machine (this VM, Linux x86_64, Python 3.12)
with `python benchmarks/bench.py`: median of 5 rounds, 1,000
iterations per round for scan and verify, 100 iterations per round
for the signing operations, against the bundled fixture project (13
components: 4 models, 2 tools, 2 MCP servers, 2 datasets, 3
prompts). The v0.1.0 run measured 677 scans/sec and 2,947
verifies/sec, so treat these as ballpark figures for a small tree,
not promises.

| Benchmark | Result |
|---|---|
| Manifest build (fixture project, 13 components) | 1.43 ms average |
| Scan throughput | 702 scans/sec |
| Verify (manifest plus file hashes) | 2,977 verifies/sec |
| Sign a manifest digest (Ed25519) | 6.67 ms average, 150 signs/sec |
| Verify a signature (Ed25519) | 9.95 ms average, 101 verifies/sec |

## What this measures, and what it does not

A scan is a directory walk, a handful of small file parses, and a
SHA-256 of every prompt and dataset file. On the fixture that is
about a millisecond and a half of work, most of it file IO. Real
projects with large datasets will be bound by hashing those files,
which is the honest cost of knowing they did not change. Verify is
the same story from the other side: digests plus re-hashing, no
parsing of dependency files, so it runs several times faster than a
scan.

Signing is the pure Python Ed25519 in `ai_bom/signing.py`, timed on
signing a manifest digest, which is the only thing this tool ever
signs. Signature verification is timed against a signature made
once before the clock starts. At roughly 7 and 10 milliseconds,
signing adds one small step at build time and verification adds one
small step at deploy time; neither belongs in a hot loop, and
neither is pretending to be a high-throughput crypto library.

The CI smoke test (`python -m ai_bom.benchmark`) uses fewer
iterations and only checks that the fixture inventory still matches
the expected counts and that the path runs, not that these exact
numbers hold.

Safe to reproduce the measurement:

```bash
pip install -e .
python benchmarks/bench.py
```
