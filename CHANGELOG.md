# Changelog

Changes that have landed on `main` but have not been included in a published
release are recorded under **Unreleased**. No numbered release history is
listed here yet; this file starts tracking the current development state and
does not imply that any release has been published.

## [Unreleased]

### Added

- Add schema-v5 project-authored overworld hidden-item records and many-to-many area links. `create-custom-overworld-hidden-item` and `delete-custom-overworld-hidden-item` default to dry-run and require `--apply` to persist; coordinate/value bounds, the `$FFFF` sentinel, area indexes, and alias links are validated. The 351 imported source rows, their source baselines, and source area relationships remain unchanged, including when the pinned source model is explicitly re-imported.
- Add a project-facing custom hidden-item create/delete API and CLI, a schema-v4-to-v5 migration with rollback coverage, and deterministic project JSON export for project-authored entries. Advance the project JSON/SQLite schema contracts to v5 and the pre-release Python package to 0.3.0.

### Fixed

- Start an explicit SQLite `BEGIN IMMEDIATE` transaction before each schema-v1-to-v5 migration step's DDL. A failed step now rolls back its partially created tables together with its version metadata; a failure-injection regression test covers a mid-DDL error. Earlier successfully committed steps in a multi-version upgrade remain valid and retryable.

### Changed

- Trace the recorded YAZE v0.7.2 out-of-range map-read offset (1,311,049) to the unconditional `LoadDiggableTiles()` read of ZSCustomOverworld v3 settings address `0x140149`, not to screen 0x50 map data. Trace the malformed staircase label to a dangling pointer from a temporary `absl::StrCat()` string stored in a public `const char*` field. Record upstream corrections `566d7c6` (2026-09-29) and `8d4f1ad` (2026-10-13); keep the updated-build runtime retest open.
- Record the 2026-10-29 user-run YAZE v0.7.2 read-only smoke test against the local ROM: ROM info, raw ROM bytes, dungeon room/sprite inspection, hex reads, overworld/dungeon palette reads, and message list/search succeeded. The screen-80 overworld map read failed with an out-of-range offset; `dungeon-get-palette` was not a supported command, while `palette-get-colors --group=dungeon_main` worked. The ROM SHA-256 remained `66871d66be19ad2c34c927d6b14cd8eb6fc3181965b6e517cb361f7316009cfb`. Partial read capability only; no ROM writes or full integration are claimed.
- Advance the pre-release package version to `0.2.0` for the second bounded semantic authoring model.
- Add SQLite-backed editing for the 168 packed dungeon chest records, preserving source fields alongside editable item byte, room value, and big-chest flag. Recompose the raw 24-bit value on edits; keep item names unresolved and candidate ROM offsets unverified.

- Advance the pre-release package version to `0.1.0` for the first public semantic authoring model and its CLI.
- Add the first project-local semantic editing model for overworld hidden items. Schema and project JSON advance to v3; explicit migrations support both v1→v2→v3 and v2→v3. Import preserves source values/coordinates and the pinned consumer classification, area aliases become ordered foreign-key relationships, and constrained record updates refresh canonical JSON. These changes do not write the ROM or assign canonical item IDs.

- Change dungeon-room pointer verification to compare target addresses against sequential payload layout, anchored at each inventory's first annotated offset and advanced by declared payload sizes. Report v2 preserves six conflicting source-comment offsets as findings instead of rewriting the source annotations.
- Change text-dictionary pointer verification so the terminal pointer uses the exclusive end of the pinned inclusive data range. Report v2 keeps both the raw terminal comment and computed target basis; the separate `.You` extent warning remains visible, and ROM provenance is not established.
- Record the 2026-10-29 user-run read-only ROM bundle: all ten checks returned success, including 320 dungeon pointers and 98 dictionary pointers with zero byte mismatches. Preserve six dungeon source-offset findings, the `.You` source-extent warning, seven text-source warnings, and 98 unresolved scalar-table expressions. The same user's ROM fingerprint matches the published No-Intro USA entry, and the user confirms it boots; document these as byte-identity and manual-boot evidence, without claiming independent chain of custody.
- Add a read-only fingerprint comparison against the published No-Intro USA entry. The user ran the check and confirmed that size, CRC-32, SHA-1, and MD5 all match the documented reference; the user separately confirms that the image boots.

- Make the overworld payload layout audit fail closed unless both inventories match the pinned disassembly revision `347c23f9fc019c72d32da537c9cb235f468d021d` and the expected 82/42 Bank0B/Bank0C pair counts. This keeps the source-log/consumer line references and fixed version-1 report schema honest; generic pair validation remains revision-agnostic.

- Make pointer-table extraction reject duplicate requested labels with source line diagnostics instead of silently parsing the first matching table.

- Mark ADR 0001 as Accepted to match the adopted SQLite canonical project format with JSON export documented in the roadmap and project-format guide.

### Added

- Add `audit-project-dungeon-chest-room-references` and a strict version-1 report schema. The project-aware audit joins edited chest room values to the pinned object/door pointer inventories while preserving each source room value and edit status; candidate offsets and room payload bytes remain unverified, and no ROM bytes are read or written.
- Expand project-aware chest-audit regression coverage for in-range edits, mismatched object/door target labels, and exclusive report-file creation without overwriting prior output.
- Add `scripts/verify-rom-readonly.sh` to run the local image inspection, self-diff, scalar-table, hidden-item, dungeon-pointer, dictionary-pointer, and text-message checks in one report-preserving pass. It requires a headerless 1 MiB image before byte comparisons, writes no ROM data, and records every check's exit status.
- Add `zelda-suite audit-overworld-hidden-item-value-semantics` and a version-1 schema. The source-only audit checks the pinned `Overworld_RevealSecret` consumer, distinguishes ordinary secret-state-mask bytes from extended low-nibble selectors, and retains the four raw `Overworld_SecretTileType` words/comments without resolving canonical item IDs or claiming ROM verification.
- Add `zelda-suite audit-dungeon-chest-room-references` and a version-1 schema to join all 168 packed chest room values with the corresponding object/door pointer slots. The pinned `Bank01.asm` consumer explicitly compares the chest room field with `$A0` and indexes the pointer tables using `$A0 * 3`; ROM offsets, payload bytes, item names, and playable-room status remain unverified.
- Add `zelda-suite audit-dungeon-room-door-pointers`, a deterministic source-only report for all 320 door-pointer addends, corresponding object-pointer slot labels, and source-declared room-payload bounds. It preserves unreferenced target findings and explicitly does not verify offsets or bytes against a ROM.
- Add `potion-shop-transactions`, a three-entry source catalog for green, blue, and red potion purchases. `inspect-potion-shop-transactions` preserves source compare/deduction literals, empty-bottle check lines, and receipt indexes `$2F/$30/$2E`; `audit-potion-shop-transactions` joins these to raw receive-item slots and graphics-comment annotations. Runtime prices and canonical item IDs are not verified.
- Add `special-shop-transactions` for Bomb Shop Bomb, Bomb Shop Super Bomb, and the Bottle Vendor bottle sale. The strict parser preserves the 100-rupee purchase paths, the two receipt selectors (`$28` and `$16`), and the Super Bomb's direct flag/tagalong reward; the audit joins only actual receipt selectors to raw receipt slots and graphics-comment annotations.
- Add `paid-overworld-interactions` for seven source-coded fee interactions and variable price tables across Fortune Teller, Digging Game, Zora King, Kiki, Archery Game, and Lake Hylia Fairy. Preserve the Digging Game reward dispatch, raw basic-item pool, and separate heart-piece gate; runtime fees and reward probabilities remain unverified.
- Add `audit-overworld-payload-layout` to cross-reference all 124 High/Low screen pairs and report the three range/size mismatches, Screen4F High's missing range, and candidate source-range adjacency. Source-log and consumer references are documented; payload decoding and trusted-ROM verification remain open.

- Add `audit-item-receipt-annotations`, which audits the 76 dense `.item_graphics_indices` slots against source-comment IDs and labels, reports missing comment ID `$40` and 12 positional/comment-ID mismatches, and exposes raw annotations in shop handler audit rows without promoting them to canonical IDs.

- Add `shop-item-handlers`, a seven-entry source catalog of standard `Sprite_ShopKeeper` purchases. `inspect-shop-item-handlers` preserves A/Y price literals and source lines; `audit-shop-item-handlers` joins receipt selectors to raw receive-item layout slots. Source handler addresses/prices remain unverified against a ROM, and the catalog does not infer room-specific shop stock or semantic item names.

- Register 168 packed `Dungeon_ChestData` records and add `inspect-dungeon-chest-data` plus `audit-dungeon-chest-data`. The export preserves raw three-byte values and exposes the source-commented top-byte item value, low-15-bit room value, and bit-15 big-chest flag. The audit reports repeated room values and item-value frequencies; offsets and item names remain unverified.

- Export the 243 source-commented `SpritePrep_Main` dispatch entries and add strict source-export validation, an `inspect-sprite-prep-dispatch` command, and `audit-sprite-prep-dispatch` to join sprite IDs with the existing 68-entry SpriteActive3 export. Preserve the routine range annotation and wrapped comments; the inline table offset, handler address annotations, and semantic equivalence of the two dispatch stages remain unverified.

- Register the 54-word `oam-buffer-position-table` and add `zelda-suite audit-oam-allocation`, a versioned structured report grouping six region limits with 48 fallback points. Tests pin A–F selector values, all eight slots per region, the source lookup arithmetic, and refusal to overwrite reports; this remains source metadata, not runtime or ROM verification.

- Add the `landmine-oam-groups` mixed-width source export and reusable `inspect-mixed-data-table` parser for colon-separated `db`/`dw`/`dl` fields, with byte-accurate offsets and pinned-source tests. The two rows remain raw source metadata, not decoded OAM semantics or ROM-verified data.

- Register the nine-word `crystal-maiden-message-ids` export from pinned `Sprites/sprite_crystal_maiden.asm` with source-parity coverage and a regression cross-reference to all distinct IDs in the registered text-message index. Preserve the source-commented range and the unresolved local `.message_ids` mapping; no ROM verification is claimed.

- Register the eight-word `crystal-maiden-palette-words` export from pinned `Sprites/sprite_crystal_maiden.asm` with parser parity and literal baselines. Preserve the raw 16-bit values and explicitly document the unresolved relationship between `CrystalMaiden_Configure_palette` and the routine's `.palette` reference; no color decoding or ROM verification is claimed.

- Register the two-entry `crystal-switch-palette-selectors` table with pinned-source parser parity for both the data bytes and its bit-indexed consumer. The values are sprite-property selector bits, not decoded palette colors or locally verified ROM bytes.

- Register the eight-byte `mad-batter-pseudo-attack-palettes` table with pinned-source parser parity and a literal-value baseline. The bytes select sprite palette fields; they are not decoded color-palette data and have not been verified against a local ROM.

- Add a source-only bounds regression joining all 320 door-pointer addends to the registered room-payload `Size:` annotations. All current addends fit their candidate target declarations; the check validates metadata arithmetic only and does not verify payload bytes, ROM offsets, or door semantics.

- Register the 320-entry source-only `dungeon-room-door-pointers` export from `RoomData_DoorDataPointers`. Pinned-source parity and submodule-independent slot-alignment tests preserve raw numeric addends without resolving their meaning or claiming local-ROM verification.

- Add read-only `zelda-suite verify-text-message-bytes` and a version-1
  report schema to compare literal encoded bytes in the 397 indexed text messages
  against a local ROM using sequential source-derived offsets. Synthetic and
  pinned-source tests cover byte mismatch reporting and preserve the source
  offset-comment and block-size warnings; the report does not decode text or
  verify ROM provenance/source-offset trust.

- Add read-only `zelda-suite verify-text-dictionary-pointers` and a strict
  version-1 report schema to compare the 98 dictionary pointer words with
  source-offset-derived LoROM candidates. Synthetic fixtures test matching and
  mismatching bytes; ROM provenance, source offsets, fragment payload bytes,
  and the runtime symbol-name mapping remain unverified.

- Add source-only `zelda-suite audit-dungeon-room-assets` and a version-1
  schema to cross-reference the 320 dungeon pointer slots with the three
  registered room payload inventories. The report preserves the three known
  unreferenced payload labels and does not read ROM or room bytes.

- Normalize eight older registered JSON exports to canonical sorted-key JSON and
  add a registry-wide regression test for byte-stable serialization across all
  registered assets, preserving array order and source values.

- Add a submodule-independent regression baseline for the committed 128-entry
  overworld hidden-item pointer table. It pins all 80 target labels, sequential
  two-byte offsets, and the 64-singleton/16-quadruple label distribution without
  claiming target resolution or ROM verification.

- Add a submodule-independent regression baseline for the committed 68-entry
  sprite dispatch export, pinning the source ID/offset range and six handler
  alias groups while preserving handler-address comments as unverified metadata.

- Add source-only `zelda-suite audit-music-assets` report and schema to join
  registered music pointer expressions with payload declarations, surfacing the
  unmatched `Song0B_FairyTheme` target and three missing payload size annotations.
  It does not read audio bytes or verify pointer offsets against a ROM.

- Add source-only `zelda-suite audit-text-message-index` diagnostics and a
  version-1 schema for known source offset-comment and block-size discrepancies
  across the committed 397-message index; no ROM bytes or decoded text are read.

- Add regression tests confirming that the dictionary asset loader rejects
  inconsistent adjacent-fragment offsets and source-extent arithmetic before
  `zelda-suite audit-text-dictionary` runs. The known `.You` source-extent
  mismatch remains a diagnostic warning; the checks do not verify ROM offsets.

- Add an integration regression baseline for all 19 registered scalar-table
  exports: 760 entries, 585 direct numeric literals, 77 negative decimal literals,
  and 98 unresolved symbols. The Mad Batter, Crystal Switch, and Crystal Maiden
  palette tables plus the Crystal Maiden message-ID table contribute 27 direct
  numeric literals total; the OAM table contributes 54 more direct numeric
  literals. The baseline remains source-only and does not claim any skipped
  expression has been resolved or verified against ROM bytes.

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
