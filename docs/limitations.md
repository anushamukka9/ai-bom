# Honest limitations

What this tool does not do, stated plainly so nobody finds out the
hard way.

- **Static discovery only.** ai-bom reads files. It does not run
  your agent, trace its calls, or watch its network traffic. A model
  or tool your code fetches at runtime leaves no file signal. If it
  matters, declare it in `aibom.json`; that is what the declaration
  file is for.
- **The known-package table is small and opinionated.** Dependencies
  and imports are mapped through a table of common provider and
  framework packages. Anything outside the table is ignored rather
  than guessed at, which means a hand-rolled HTTP client calling a
  model API shows up only if you declare the model.
- **Hashing covers files, not remote services.** A hosted model, a
  remote MCP server, or a dataset behind a URL is inventoried by
  name and declared version. If the provider swaps the model behind
  the name, nothing here notices. Pin versions where the provider
  lets you, and treat the manifest as a record of what you asked
  for, not proof of what ran.
- **Unsigned in v1.** The SHA-256 digests detect edits when the
  digest you trust lives somewhere the manifest writer cannot
  reach. Anyone who can rewrite the manifest file can also recompute
  its digests and produce a self-consistent fake; verify without a
  pinned digest proves consistency, not provenance. Ed25519 signing
  and verification are on the roadmap for the next release. v1 does
  not produce or check signatures.
- **The timestamp is not digest-protected.** `generated_at` and
  `generator` sit outside the digest payload so rescans of an
  unchanged project keep the same digest. The cost: those two fields
  can be edited without tripping verify. The component list, which
  is the part that matters, cannot.
- **MCP verification is per server entry.** Each server's hash
  covers its own config entry. Adding a brand new server to a config
  does not fail verify for the existing ones; it shows up in the
  next scan and in `diff`, which is where additions belong.
- **Dataset contents are never inspected.** Name, path, size, and
  hash only. The manifest cannot tell you a dataset is poisoned,
  mislicensed, stale, or full of personal data.
- **Prompt detection is by location and extension.** A prompt string
  built inline in code is code, not a prompt file, and it is not
  inventoried. Move prompts into files if you want them counted;
  most agent codebases are better for it anyway.
- **Versions are only as good as their sources.** A pinned
  requirement records its pin. A range records nothing, because the
  resolved version lives in your environment, not in the tree.

None of this makes the tool useless. It makes it an inventory with
a tripwire, which is the job most agent setups actually need done:
a list you can diff, and a digest that tells you when the list or
the files behind it moved. Claim more than that for it and you will
be disappointed in exactly the ways listed above.
