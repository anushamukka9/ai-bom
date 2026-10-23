"""CI smoke benchmark: build manifests for the fixture project.

Run with: python -m ai_bom.benchmark

Asserts the fixture inventory matches the expected counts, then
times repeated scans. The full benchmark in ``benchmarks/bench.py``
runs more iterations and is what ``benchmarks/results.md`` records.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from ai_bom.discovery import scan_project
from ai_bom.fixture import EXPECTED_COUNTS, build_fixture_project
from ai_bom.verify import verify_manifest


def bench_scan(iterations: int = 50, root: Path | None = None) -> float:
    """Return fixture scans per second."""
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            return bench_scan(iterations=iterations, root=Path(tmp))
    fixture = build_fixture_project(root / "fixture-project")
    manifest = scan_project(fixture, generated_at="2026-01-01T00:00:00Z")
    counts = manifest.counts()
    assert counts == EXPECTED_COUNTS, f"fixture counts drifted: {counts}"
    result = verify_manifest(manifest, fixture)
    assert result.valid, f"fresh manifest failed verification: {result.problems}"
    start = time.perf_counter()
    for _ in range(iterations):
        scan_project(fixture, generated_at="2026-01-01T00:00:00Z")
    elapsed = time.perf_counter() - start
    return iterations / elapsed


def main() -> None:
    rate = bench_scan()
    total = sum(EXPECTED_COUNTS.values())
    print(f"fixture components: {total} (counts match expected per category)")
    print(f"scan throughput: {rate:,.1f} scans/sec")
    print(f"average scan time: {1000.0 / rate:,.2f} ms")
    print("benchmark smoke test passed")


if __name__ == "__main__":
    main()
