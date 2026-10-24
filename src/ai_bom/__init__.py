"""ai-bom: an AI Bill of Materials for agent apps.

One command inventories your models, tools, MCP servers, datasets,
and prompts into a manifest with a tamper-evident SHA-256 digest,
optionally signed with Ed25519 so a rewritten manifest cannot pass
as the original. Know what your agent is made of before it runs.

Quickstart:
    from ai_bom import scan_project, verify_manifest

    manifest = scan_project("my-agent-app")
    print(manifest.counts())
    print(manifest.digest)

    result = verify_manifest(manifest, "my-agent-app")
    assert result.valid
"""

from ai_bom.diff import ComponentChange, Diff, diff_manifests
from ai_bom.discovery import KNOWN_PACKAGES, scan_project, sha256_file
from ai_bom.models import CATEGORIES, SCHEMA_VERSION, Component, Manifest
from ai_bom.signing import (
    Signature,
    derive_public_key,
    generate_keypair,
    load_private_key,
    load_public_key,
    sign_manifest,
    verify,
)
from ai_bom.verify import VerifyResult, verify_manifest

__version__ = "0.2.0"

__all__ = [
    "CATEGORIES",
    "KNOWN_PACKAGES",
    "SCHEMA_VERSION",
    "Component",
    "ComponentChange",
    "Diff",
    "Manifest",
    "Signature",
    "VerifyResult",
    "derive_public_key",
    "diff_manifests",
    "generate_keypair",
    "load_private_key",
    "load_public_key",
    "scan_project",
    "sha256_file",
    "sign_manifest",
    "verify",
    "verify_manifest",
]
