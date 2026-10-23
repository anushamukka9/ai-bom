"""Command line interface: the `ai-bom` console script.

Commands:

- ``ai-bom scan <path> [--output FILE] [--format json|markdown]``
- ``ai-bom verify <manifest> [path]``
- ``ai-bom show <manifest>``
- ``ai-bom diff <old> <new>``

Exit codes, everywhere:

- 0: success. For verify, the manifest checks out. For diff, the two
  manifests are identical.
- 1: verify found tampering or drift, or diff found differences.
  This is a finding, not a crash.
- 2: usage or input error: a missing path, an unreadable file, or a
  manifest that does not parse. Nothing was checked.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ai_bom import __version__
from ai_bom.diff import diff_manifests
from ai_bom.discovery import scan_project
from ai_bom.models import CATEGORIES, Manifest
from ai_bom.verify import verify_manifest

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2


def _load_manifest(path_str: str) -> Manifest:
    path = Path(path_str)
    if not path.is_file():
        raise FileNotFoundError(f"manifest not found: {path_str}")
    return Manifest.from_json(path.read_text(encoding="utf-8"))


def render_markdown(manifest: Manifest) -> str:
    counts = manifest.counts()
    lines = [
        f"# AI Bill of Materials: {manifest.project}",
        "",
        f"Generated: {manifest.generated_at} by {manifest.generator}",
        f"Manifest digest (SHA-256): {manifest.digest}",
        "",
        "| Category | Count |",
        "|---|---|",
    ]
    for category in CATEGORIES:
        lines.append(f"| {category} | {counts[category]} |")
    lines.append(f"| **total** | **{sum(counts.values())}** |")
    for category in CATEGORIES:
        comps = [c for c in manifest.sorted_components() if c.category == category]
        if not comps:
            continue
        lines += [
            "",
            f"## {category}",
            "",
            "| Name | Version | Source | SHA-256 |",
            "|---|---|---|---|",
        ]
        for comp in comps:
            sha = comp.sha256[:12] + "..." if comp.sha256 else "-"
            lines.append(f"| {comp.name} | {comp.version or '-'} | {comp.source} | {sha} |")
    lines.append("")
    return "\n".join(lines)


def render_summary(manifest: Manifest) -> str:
    counts = manifest.counts()
    lines = [
        f"project: {manifest.project}",
        f"schema: {manifest.schema_version}",
        f"generated: {manifest.generated_at} by {manifest.generator}",
        f"digest: {manifest.digest}",
        f"components: {sum(counts.values())} total",
    ]
    for category in CATEGORIES:
        comps = [c for c in manifest.sorted_components() if c.category == category]
        if not comps:
            continue
        lines.append(f"  {category}: {len(comps)}")
        for comp in comps:
            bits = [comp.name]
            if comp.version:
                bits.append(f"version {comp.version}")
            bits.append(f"from {comp.source}")
            if comp.sha256:
                bits.append(f"sha256 {comp.sha256[:12]}...")
            lines.append("    - " + ", ".join(bits))
    return "\n".join(lines)


def cmd_scan(args: argparse.Namespace) -> int:
    root = Path(args.path)
    if not root.is_dir():
        print(f"error: not a directory: {args.path}", file=sys.stderr)
        return EXIT_USAGE
    manifest = scan_project(root)
    if args.format == "markdown":
        output = render_markdown(manifest)
    else:
        output = manifest.to_json()
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        counts = manifest.counts()
        total = sum(counts.values())
        print(f"wrote {args.output}: {total} components, digest {manifest.digest[:16]}...")
    else:
        print(output, end="" if output.endswith("\n") else "\n")
    return EXIT_OK


def cmd_verify(args: argparse.Namespace) -> int:
    try:
        manifest = _load_manifest(args.manifest)
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"error: cannot load manifest: {exc}", file=sys.stderr)
        return EXIT_USAGE
    root = None
    if args.path:
        root = Path(args.path)
        if not root.is_dir():
            print(f"error: not a directory: {args.path}", file=sys.stderr)
            return EXIT_USAGE
    result = verify_manifest(manifest, root)
    if result.valid:
        scope = "internal digests and file hashes" if root else "internal digests only"
        print(f"verify ok: manifest is valid ({scope}, {result.checked_files} files checked)")
        return EXIT_OK
    print("verify FAILED:", file=sys.stderr)
    for problem in result.problems:
        print(f"  - {problem}", file=sys.stderr)
    return EXIT_FINDINGS


def cmd_show(args: argparse.Namespace) -> int:
    try:
        manifest = _load_manifest(args.manifest)
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"error: cannot load manifest: {exc}", file=sys.stderr)
        return EXIT_USAGE
    print(render_summary(manifest))
    return EXIT_OK


def cmd_diff(args: argparse.Namespace) -> int:
    try:
        old = _load_manifest(args.old)
        new = _load_manifest(args.new)
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"error: cannot load manifest: {exc}", file=sys.stderr)
        return EXIT_USAGE
    diff = diff_manifests(old, new)
    if args.format == "json":
        print(json.dumps(diff.to_dict(), indent=2))
    else:
        if not diff.has_changes:
            print("diff: no differences")
        for comp in diff.added:
            print(f"  added:   {comp.category}/{comp.name}")
        for comp in diff.removed:
            print(f"  removed: {comp.category}/{comp.name}")
        for change in diff.changed:
            fields = ", ".join(change.fields)
            print(f"  changed: {change.after.category}/{change.after.name} ({fields})")
    return EXIT_FINDINGS if diff.has_changes else EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-bom",
        description="AI Bill of Materials for agent apps.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="scan a project and build its manifest")
    p_scan.add_argument("path", help="project directory to scan")
    p_scan.add_argument("--output", "-o", default=None, help="write the manifest here")
    p_scan.add_argument("--format", choices=["json", "markdown"], default="json")
    p_scan.set_defaults(func=cmd_scan)

    p_verify = sub.add_parser("verify", help="check a manifest for tampering or drift")
    p_verify.add_argument("manifest", help="manifest JSON file")
    p_verify.add_argument(
        "path", nargs="?", default=None, help="project directory to check files against"
    )
    p_verify.set_defaults(func=cmd_verify)

    p_show = sub.add_parser("show", help="print a readable summary of a manifest")
    p_show.add_argument("manifest", help="manifest JSON file")
    p_show.set_defaults(func=cmd_show)

    p_diff = sub.add_parser("diff", help="compare two manifests")
    p_diff.add_argument("old", help="older manifest JSON file")
    p_diff.add_argument("new", help="newer manifest JSON file")
    p_diff.add_argument("--format", choices=["text", "json"], default="text")
    p_diff.set_defaults(func=cmd_diff)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
