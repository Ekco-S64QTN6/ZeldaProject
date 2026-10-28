# Contributing to ZeldaProject

This repository is in Phase 1: structured source extraction. Contributions
should make source-derived metadata auditable and reproducible without claiming
that source comments, source symbols, or computed offsets have been verified
against a ROM unless that verification was actually performed.

## Development setup and checks

Use Python 3.12 and install the project's development dependencies:

```bash
uv sync
uv run zelda-suite --help
python -m compileall -q src tests
python -m pytest -q
```

CI runs syntax checking, Ruff across all Python files in `src` and `tests`,
strict MyPy checking for `src`, and the full pytest suite. The wheel packaging
and cross-platform setup smoke jobs also run in CI. New Python source and test
files are included automatically because linting targets the directories.

Run targeted tests while iterating, then run the full suite before requesting
review. The checked-in disassembly submodule is pinned; source-parity tests
must use that revision rather than silently updating to a newer upstream tree.

## Adding a source-derived inventory

1. **Identify the exact source and revision.** Record the source filename,
   source label or table boundary, and pinned disassembly revision. Keep ROM
   file offsets, SPC RAM addresses, CPU addresses, and other address domains
   as different fields.
2. **Use bounded parsing.** Reuse an existing extractor where possible:
   `inspect-pointer-table`, `inspect-data-table`, `inspect-incbin`,
   `inspect-text-dictionary`, `inspect-text-messages`,
   `inspect-sprite-dispatch`, `inspect-music-track-index`, or
   `inspect-overworld-hidden-items` for the pinned hidden-item source layout.
   Do not add a second parser for a format that the existing parser already
   represents.
   If a new format is necessary, define a strict, versioned export contract.
3. **Preserve source facts.** Keep raw expressions, labels, source lines,
   source revision, explicit source annotations, and nullable/unknown values.
   Never execute arbitrary assembler expressions or silently repair a source
   comment. Keep calculated fields separate from fields explicitly stated in
   source. A computed end offset is not evidence that the source range is
   correct.
4. **Add tests at two levels.** Add synthetic fixtures for parser edge cases
   (missing boundaries, duplicate labels, malformed expressions, aliases or
   null entries as appropriate), and parser-parity tests that compare the
   committed export with the pinned source. When assets are related, add an
   explicit cross-reference invariant and document any unmatched symbols.
5. **Validate the export.** Generate to a temporary output path, run
   `zelda-suite validate-source-export`, and compare it with the committed
   version. CLI output paths intentionally refuse to overwrite existing files.
   Use `zelda-suite audit-unresolved-table-expressions` to review unresolved
   expressions across the registered scalar tables. The audit preserves raw
   source text and does not execute or resolve assembler syntax.
   When working with registered `incbin` exports, also run
   `zelda-suite audit-incbin-inventory` and review metadata gaps, source-range
   mismatches, and candidate overlaps. These are diagnostics only and must not
   be used to silently rewrite source annotations or claim ROM verification.
6. **Register the asset.** Add a unique kebab-case entry and unique JSON file
   in `data/extracted/manifest.json`, with the correct format, source revision,
   record count, subsystem, and concise description. Extend the loader's
   strict validator, supported-format list, count-field mapping, and exported
   constants only when the format requires it. Update
   `docs/schemas/asset-registry.schema.json` and add a versioned format schema
   when introducing a new export format.
7. **Document the result.** Update `docs/extracted-data.md`, the relevant
   subsystem discovery page, and `ROADMAP.md` in the same change. Explain
   regeneration commands, counts, known discrepancies, and what is not
   verified. Update `README.md` or `CLAUDE.md` when user-facing workflows,
   architecture, or agent instructions change.

## ROM and binary-data guardrails

- Never commit ROM images, partial ROM slices, extracted ROM bytes, or binary
  `incbin` payloads. The repository commits source declarations and metadata
  only; referenced binary payload files may not exist in the pinned submodule.
- Use only a locally supplied clean US ROM for ROM-dependent verification.
  Do not download, redistribute, or add a ROM to Git. Record the file's hash
  and header assessment when an authorized local verification is performed.
- Do not mark source-commented offsets as verified ROM locations unless the
  corresponding bytes were independently checked against the local ROM.
- Do not infer semantic item IDs, playable-room counts, map layers, pointer
  targets, or audio payload availability solely from a source label or comment.
- Do not implement ROM writes until there is verified address mapping,
  deterministic dry-run/diff output, bounds and reference checks, and an
  emulator or equivalent execution smoke test.
- Project imports should use
  `zelda-suite import-extracted-asset PROJECT.db asset-name` for committed
  assets so registry format, revision, safe filename, and record count are
  validated. Use `import-source-asset` only for an unregistered but validated
  source export. Replacing an existing project key requires the explicit
  `--replace` flag.

## Versioning and change notes

Record each behavior or contract change under `[Unreleased]` in
[`CHANGELOG.md`](./CHANGELOG.md). Use [the versioning policy](./docs/versioning.md)
to distinguish package releases, project JSON, SQLite schema, registry, and
source-export format versions; do not bump one merely because another changed.

## Branch and pull-request lifecycle

Start each focused change on one short-lived branch from the latest `main`.
Before reusing an old branch, compare its unique commits with `main`; ahead
counts do not mean those commits are missing functionality, and a heavily
diverged branch should not be merged wholesale to recover one change. The repo
has GitHub's `delete_branch_on_merge` setting enabled, so branches merged via
PR should be removed automatically. If a branch remains afterward, treat it as
an orphaned/stale branch and review it separately rather than continuing work
on it.

## Pull request checklist

Before requesting review, confirm that the change:

- [ ] Has a clear Roadmap item or explains why it is necessary groundwork.
- [ ] Preserves source expressions and annotates unknown/unverified values.
- [ ] Includes synthetic tests and pinned-source parity tests where applicable.
- [ ] Updates the manifest/schema/loader when needed and adds tests for new invariants.
- [ ] Updates relevant documentation and regeneration commands.
- [ ] Updates `CHANGELOG.md` and any version/schema contract described by the change.
- [ ] Adds no ROM or ROM-derived binary data.
- [ ] Keeps setup automation ROM-independent and tests safe refusal to overwrite existing project files, where applicable.
- [ ] Passes `python -m compileall -q src tests`, Ruff on the changed Python
      components, `python -m mypy src`, and `python -m pytest -q`.

A green CI run is required before merging. If a check cannot run because a local
ROM or external tool is unavailable, leave the Roadmap gate open and say so
explicitly rather than replacing it with a source-only approximation.


For text dictionary changes, also run `uv run zelda-suite audit-text-dictionary` and review both pointer-to-fragment label coverage and source-extent warnings. The audit uses committed metadata only; do not resolve pointer values or rewrite the `.You` extent annotation without separate source/ROM evidence.


For text-message index changes, also run `uv run zelda-suite audit-text-message-index`. Review malformed/mismatched offset annotations and block-size differences, but do not “repair” source-derived metadata without checking the pinned source and a trusted local ROM. The audit does not read ROM bytes or decode messages.


For music source-index or payload-inventory changes, also run `uv run zelda-suite audit-music-assets`. Review unmatched target labels, unreferenced declarations, and missing size annotations; do not infer payload availability or semantic audio meaning from source labels alone.


The committed sprite dispatch export has a source-independent baseline test. If its IDs, offsets, or handler alias groups change, review the raw export diff and update the baseline with the same source revision; handler addresses in comments are not ROM-verified pointers.


The committed `overworld-hidden-item-pointers` export has a submodule-independent baseline test. When updating it intentionally, review the complete 80-label target set, all 128 slot offsets, and the repeated-target distribution; the test does not verify pointer values against ROM bytes.


For any change to `data/extracted/*.json`, run the complete asset-loader tests.
Every registered export must match the canonical UTF-8 JSON representation:
two-space indentation, sorted object keys, array order preserved, no non-standard
numbers, and a final newline. Prefer regenerating exports through their parser
CLI; if normalizing an older export, review that the change is key order or
formatting only and that no data values or arrays changed.
