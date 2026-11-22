# Examples

- `quickstart.py`: scans the example project, prints the manifest
  summary, verifies it against the files on disk, and diffs a rescan
  against the first scan. Run it with `python examples/quickstart.py`.
- `signing_demo.py`: generates a throwaway Ed25519 keypair, signs a
  manifest, verifies it the way a deploy step would, then shows a
  tampered manifest and a manifest re-signed by another key both
  failing. Run it with `python examples/signing_demo.py`.
- `cyclonedx_export.py`: scans the example project, converts the
  manifest to CycloneDX 1.5, and writes `example-cyclonedx.json`.
  Run it with `python examples/cyclonedx_export.py`.
- `example-cyclonedx.json`: the CycloneDX export of the example
  project, ready to feed to SBOM tooling.
- `ci-verify-signed.yml`: a GitHub Actions job that verifies a
  signed manifest with `--require-signature` and a pinned public
  key, ready to copy into a consuming repo.
- `example_project/`: a tiny fake support agent that exists to be
  inventoried. Its README lists exactly what a scan should find, and
  a test holds the scanner to that list.
