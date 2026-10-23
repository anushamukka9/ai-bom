"""Thirty-second demo: scan the example project, verify it, diff it.

Run: python examples/quickstart.py

Scans examples/example_project into a manifest, prints the summary
and the digest, verifies the manifest against the files on disk,
then edits nothing and rescans to show a clean diff. Edit a prompt
file between scans in your own copy and watch verify fail instead.
"""

from pathlib import Path

from ai_bom import diff_manifests, scan_project, verify_manifest
from ai_bom.cli import render_summary

HERE = Path(__file__).resolve().parent
PROJECT = HERE / "example_project"

manifest = scan_project(PROJECT)
print(render_summary(manifest))
print()

result = verify_manifest(manifest, PROJECT)
print(f"verify against the project on disk: valid={result.valid}")
assert result.valid

again = scan_project(PROJECT)
diff = diff_manifests(manifest, again)
print(f"rescan diff (timestamps differ, contents do not): has_changes={diff.has_changes}")
assert not diff.has_changes

print("done. one command made the list, one digest keeps it honest.")
