# Changelog

Changes that have landed on `main` but have not been included in a published
release are recorded under **Unreleased**. No numbered release history is
listed here yet; this file starts tracking the current development state and
does not imply that any release has been published.

## [Unreleased]

### Added

- Add source-only `zelda-suite audit-music-assets` report and schema to join
  registered music pointer expressions with payload declarations, surfacing the
  unmatched `Song0B_FairyTheme` target and three missing payload size annotations.
  It does not read audio bytes or verify pointer offsets against a ROM.

- Add source-only `zelda-suite audit-text-message-index` diagnostics and a
  version-1 schema for known source offset-comment and block-size discrepancies
  across the committed 397-message index; no ROM bytes or decoded text are read.

- Add a source-only `zelda-suite audit-text-dictionary` report and version-1
  schema to cross-check registered pointer expressions and fragment records;
  the known `.You` source-extent mismatch remains a diagnostic warning.

- Add an integration regression baseline for all 14 registered scalar-table
  exports: 679 entries, 504 direct numeric literals, 77 negative decimal literals,
  and 98 unresolved symbols. The baseline is source-only and does not claim that
  any skipped expression has been resolved or verified against ROM bytes.

- Pin the current six-inventory `audit-incbin-inventory` summary in an integration test, so metadata gaps, range/size discrepancies, and candidate-overlap counts cannot drift silently. The baseline is source-only and does not verify ROM offsets.

- ROM-independent `zelda-suite audit-unresolved-table-expressions` report
  and strict version-1 schema for unresolved registered scalar-table expressions.
  It preserves raw text and source locations and classifies syntax shape without
  evaluating assembler expressions.

- Source-only `zelda-suite audit-incbin-inventory` report and strict version-1
  schema for metadata gaps, source range/size mismatches, and candidate span
  overlaps across registered `incbin` inventories. Findings are diagnostic and
  do not verify ROM offsets or payload bytes.

- Opt-in `zelda-suite verify-rom-tables --include-skipped-expressions` report
  format v2, which enumerates unresolved expressions with source table indices,
  lines, offsets, and conservative syntax classifications without evaluating
  assembler expressions. The default report format v1 remains unchanged.

- Optional `zelda-suite inspect-data-table --entry-count N` and parser-level
  expected-count validation so known table sizes can be asserted explicitly.
- Read-only `zelda-suite verify-rom-tables ROM` command and a versioned JSON
  report for comparing registered scalar-table literals with a local ROM.
  Simple negative decimal expressions are compared as signed-width
  two's-complement values; other unresolved expressions remain skipped.
- Read-only `zelda-suite verify-overworld-hidden-items ROM` report for
  comparing 128 source-derived pointer words, mixed-width record/sentinel
  bytes, and four replacement Map16 words, with per-area list grouping based
  on the consumer's sentinel scan.
- Read-only `zelda-suite verify-dungeon-room-pointers ROM` report for comparing
  320 three-byte room pointer values against candidate LoROM addresses derived
  from the three registered payload inventories. The report does not claim
  source-offset trust, payload byte verification, or playable-room resolution.
- ROM-independent `zelda-suite inspect-overworld-hidden-items` JSON report for the pinned source layout, including pointer entries, labels, raw records, sentinels, and area groupings. It marks ROM verification and semantic decoding as false.
- Registered `item-receipt-layout` joined view plus a strict versioned schema
  and `zelda-suite join-item-receipt-tables` command for aligning six raw
  76-entry receive-item arrays while preserving the separate 14-word dungeon
  mask table and leaving canonical semantic item IDs unresolved.
- Registered `item-receipt-graphics-indices` as a version-2 raw table export,
  preserving each source inline comment while keeping dense byte positions
  separate from comment IDs that skip `0x40`.
- A staged, read-only local-ROM verification runbook covering file inspection,
  self-diff smoke testing, scalar-table byte comparisons, clear reporting for
  skipped/unresolved entries, and external-tool installation/capability checks.
- Source-derived, manifest-registered metadata inventories for the currently
  covered falling-prize, text, sprite dispatch, music, overworld, receive-item,
  and dungeon room-pointer/payload declarations. Source annotations and
  unresolved values remain explicit; ROM bytes and binary `incbin` payloads
  are not committed.
- Read-only consistency checks for overworld High/Low payload pairs, dungeon
  pointer targets versus the union of all three room payload inventories, and
  the music pointer/payload label relationship.
- SQLite project schema v2 for importing validated source-export snapshots,
  with explicit v1-to-v2 migration, duplicate-key protection, source
  provenance, canonical JSON exports, and SHA-256 integrity checks.
- Manifest-backed project asset import by name, with registry format, source
  revision, filename, and record-count validation before persistence.
- Opt-in `zelda-suite inspect-data-table --include-comments` export format v2,
  preserving per-line inline comments while keeping the default version-1
  output contract unchanged.
- `CONTRIBUTING.md` plus this changelog and the versioning policy.
- Cross-platform workspace setup scripts (`scripts/setup.sh` and
  `scripts/setup.ps1`) that prepare dependencies, initialize and validate a
  project, and never fetch or modify ROMs.

### Changed

- Reconciled `ROADMAP.md`, `README.md`, `CLAUDE.md`, and subsystem
  documentation with the implemented parser, registry, project-store, and
  source-inventory capabilities. Local-ROM checks include a focused byte
  comparison that matched all five falling-prize arrays and a broader
  comparison of 428 direct numeric scalar-table literals with zero mismatches;
  175 unresolved/non-numeric records were skipped. Canonical ROM provenance
  and external-tool verification remain open.
- Replaced the step-5 one-off scalar-table Python snippet with the tested
  `verify-rom-tables` CLI in the local-ROM runbook and documented the generic
  Linux YAZE archive/checksum route for Arch and other non-Debian systems.
  Existing user-run ROM results remain evidence only for the compared bytes.
- Clarified that the documented US ROM path is only a local setup convention,
  not proof that a dump exists or is valid; made the agent instructions and
  human-facing quickstart consistent with the still-open ROM/tool verification
  gates.
- Reconciled the hidden-item source region's byte accounting with the pinned
  reader's three-byte stride and `$FFFF` termination. Local-ROM verification
  and per-area grouping remain open.
- Documented the seven-entry falling-prize lookup as a joined source-only view
  over its five parallel arrays, while preserving the open local-ROM byte
  verification gate.
- Corrected the fixture-directory guide to match the actual tracked files and
  clarify that ROM images, ROM slices, and golden ROM artifacts are not
  committed or required by ROM-independent tests.

### Verification

- Added and expanded parser-parity, export-validation, project migration,
  registered-asset round-trip, dungeon-label cross-reference, music-label
  cross-reference, overworld pair-integrity, source-comment, setup fallback
  orchestration, falling-prize consumer, and hidden-item sentinel/accounting
  source tests.
- The main-branch CI suite checks Python syntax, Ruff across all Python files
  in `src` and `tests`, strict MyPy types for `src`, and the full pytest suite.
- Linux and Windows CI smoke tests execute the POSIX and PowerShell setup
  scripts respectively, create and validate SQLite/JSON project files in
  temporary workspaces, and do not require a ROM. The Python-fallback setup
  regression test isolates its PATH so a globally installed `uv` cannot
  accidentally select the wrong setup path.
- CI builds the Python wheel, installs it into a clean virtual environment, and
  smoke-tests the installed CLI by initializing and validating a project.
- Synthetic tests exercise the scalar-table verifier's match/mismatch paths,
  skipped symbolic entries, signed decimal byte encoding, distinct directive
  byte width versus entry stride, report serialization, and expected-size guard.
- Tests cover the joined receive-item export against its six registered raw
  arrays, separate dungeon masks, reproducible CLI output, and failure on
  misaligned entry offsets or false semantic-ID claims.
- Source-parity and CLI reproduction tests cover the graphics-index v2 export
  and assert that the `0x40` source-comment gap is preserved without changing
  dense `table_index` values.
- Synthetic dungeon pointer tests encode source-derived candidate target
  addresses into temporary ROMs, cover all 320 pointer entries, verify mismatch
  reporting, and test CLI JSON output and no-overwrite behavior.
- Synthetic hidden-item ROM fixtures exercise all 550 comparison spans, area
  grouping, per-kind mismatch reporting, CLI JSON output, no-overwrite
  behavior, and fail-closed parsing of changed sentinel declarations.
