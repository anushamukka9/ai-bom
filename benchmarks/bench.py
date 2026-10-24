"""Extended benchmarks for ai-bom. Prints measured numbers.

Run: python benchmarks/bench.py [--quick]
Record the output in benchmarks/results.md.

Builds the bundled fixture project (13 components across all five
categories) in a temp directory, asserts the inventory counts, then
times repeated manifest builds, verifications, and Ed25519 signing
operations (signature verification is timed against a signature made
once, before the clock starts).
"""

from __future__ import annotations

import argparse
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ai_bom.benchmark import bench_scan  # noqa: E402
from ai_bom.discovery import scan_project  # noqa: E402
from ai_bom.fixture import EXPECTED_COUNTS, build_fixture_project  # noqa: E402
from ai_bom.signing import generate_keypair, sign, signing_message, verify  # noqa: E402
from ai_bom.verify import verify_manifest  # noqa: E402


def _time(fn, iterations: int, rounds: int = 5) -> float:
    samples = []
    for _ in range(rounds):
        start = time.perf_counter()
        for _ in range(iterations):
            fn()
        samples.append(iterations / (time.perf_counter() - start))
    return statistics.median(samples)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()

    scan_iterations = 100 if args.quick else 1000
    verify_iterations = 100 if args.quick else 1000

    with tempfile.TemporaryDirectory() as tmp:
        fixture = build_fixture_project(Path(tmp) / "fixture-project")
        manifest = scan_project(fixture, generated_at="2026-01-01T00:00:00Z")
        counts = manifest.counts()
        assert counts == EXPECTED_COUNTS, f"fixture counts drifted: {counts}"
        total = sum(counts.values())
        print(f"fixture project: {total} components")
        for category, count in counts.items():
            print(f"  {category}: {count}")

        scan_rate = _time(
            lambda: scan_project(fixture, generated_at="2026-01-01T00:00:00Z"),
            scan_iterations,
        )
        verify_rate = _time(lambda: verify_manifest(manifest, fixture), verify_iterations)
        smoke_rate = bench_scan(iterations=50)

        sign_iterations = 20 if args.quick else 100
        private, public = generate_keypair()
        message = signing_message(manifest.digest)
        signature = sign(private, message)
        assert verify(public, message, signature)
        sign_rate = _time(lambda: sign(private, message), sign_iterations)
        sig_verify_rate = _time(lambda: verify(public, message, signature), sign_iterations)

    print(f"scan fixture project:   {scan_rate:>12,.1f} scans/sec")
    print(f"  average build time:   {1000.0 / scan_rate:>12,.2f} ms")
    print(f"verify manifest+files:  {verify_rate:>12,.1f} verifies/sec")
    print(f"smoke bench_scan:       {smoke_rate:>12,.1f} scans/sec")
    print(f"sign manifest digest:   {sign_rate:>12,.1f} signs/sec")
    print(f"  average sign time:    {1000.0 / sign_rate:>12,.2f} ms")
    print(f"verify signature:       {sig_verify_rate:>12,.1f} verifies/sec")
    print(f"  average verify time:  {1000.0 / sig_verify_rate:>12,.2f} ms")
    print("done")


if __name__ == "__main__":
    main()
