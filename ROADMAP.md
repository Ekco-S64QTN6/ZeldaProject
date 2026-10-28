# ZeldaProject Roadmap

**Goal:** Build a scriptable, agent-native authoring suite for *The Legend of Zelda: A Link to the Past* (SNES). The long-term target is a structured project model with semantic editing APIs, deterministic ROM builds/diffs, verification, and eventually maker-style authoring.

**Current state (2026-10-28): Phase 1 — Structured Extraction is in progress.** Phase 0 has useful scaffolding but still has environment-dependent verification gates. The repository provides source-derived metadata parsers, a named extracted-asset registry, SQLite project initialization/validation plus schema-v2 storage for validated source-export snapshots, read-only ROM inspection, and file-to-file ROM diff utilities. It does **not** yet provide semantic overworld/dungeon editors or a ROM writer/rebuilder.

Status legend: **[x] verified in repository/automated tests** · **[~] partial; limitations remain** · **[ ] not implemented or not verified in the available environment**.

## Phase 0 — Foundation

**Objective:** Establish the canonical ROM, workspace layout, project format, and low-level access primitives.

- [ ] Verify the provenance of the local US ROM and establish it as the canonical base-game ROM. ROMs remain untracked and are not included in CI. Start with [the local-ROM verification runbook](./docs/real-rom-verification.md); expected size and a SHA-256 fingerprint alone do not prove authenticity.
- [~] Verify header state and document offset mapping. `zelda-suite inspect-rom` reports file size, SHA-256, header-size assessment, and LoROM mapping; its size-based assessment is diagnostic, not proof of a canonical dump or hash.
- [ ] Install and smoke-test YAZE/`z3ed` against the locally supplied US ROM, including actual overworld, dungeon, graphics/palette, and message reads.
- [ ] Test `z3cli` with the chosen model endpoint and a real tool call; decide whether to use it or a thin custom MCP server.
- [x] Choose SQLite as the canonical project format with JSON export, recorded in the accepted [ADR 0001](./docs/decisions/0001-project-data-format.md).
- [x] Provide `zelda-suite init`, `validate`, and explicit schema-v1-to-v2 `migrate-project` for a versioned SQLite project plus canonical JSON export. The project can store validated source-export snapshots, but it is not yet the editable game-system data model.

**Exit criteria:** Not met. Local ROM provenance and real YAZE/`z3ed` and agent-harness smoke tests remain outstanding.

## Phase 1 — Structured Extraction (current focus)

**Objective:** Build a source-traceable, queryable metadata model without treating unverified source comments as confirmed ROM facts.

- [x] Add read-only parsers for source pointer tables, Asar `db`/`dw`/`dl` data tables, labelled `incbin` declarations, text dictionary fragments, text message labels, sprite dispatch, and music-track pointers. CI also pins the committed 68-entry `SpriteActive3_Table` export when the disassembly submodule is absent, including contiguous `$79–$BC` slots and its six handler alias groups; handler address comments remain source annotations.
- [x] Fail closed when a requested pointer-table label appears more than once in the source; the parser reports every matching source line rather than silently selecting the first matching block.
- [x] Export the eight-entry `MadBatter_PseudoAttackPlayer_palettes` selector table from pinned `Sprites/sprite_mad_batter.asm`; its source-parity test preserves literal selector bytes and the source-commented `$02FB86–$02FB8D` range without claiming color-palette decoding or ROM verification.
- [x] Preserve source inline comments through opt-in `inspect-data-table --include-comments` format v2; the default version-1 export remains backward-compatible and comments are validated as inert strings only.
- [x] Cross-reference the 35-slot music pointer index against the 15 declared payload labels: all 15 payload labels appear in the pointer target set, plus the distinct `Song0B_FairyTheme` target, which has no matching entry in the current `incbin` inventory. The `zelda-suite audit-music-assets` API/CLI now reports that unmatched label and the three auxiliary declarations without size annotations; these remain source metadata findings, not ROM-level payload absence or pointer resolution.
- [x] Add versioned JSON export validation and a manifest-backed named-asset loader that checks registered names, safe filenames, format, source revision, and record count. A registry-wide regression test also requires all 29 committed exports to use canonical sorted JSON, unchanged array ordering, strict JSON values, and a final newline.
- [x] Commit the source-only 320-entry dungeon room pointer table with pinned-source parser-parity coverage; do not treat its count as the number of playable rooms or as resolved ROM targets.
- [x] Commit the companion 320-entry `RoomData_DoorDataPointers` export at source-commented offset `$0F83C0`; preserve its numeric addends and pin all target labels against the matching `RoomData_ObjectDataPointers` slots. Addend meaning and local-ROM verification remain open.
- [x] Cross-reference the 320 dungeon pointer slots with all three payload inventories and pinned Bank03/Bank0A/Bank1F source labels: the inventories cover all 266 definitions, all 263 distinct pointer target labels are included, and exactly three definitions are not referenced by the table. This remains source-symbol verification, not ROM pointer resolution. Add the source-only `zelda-suite audit-dungeon-room-assets` command and CI baseline so the committed JSON relationships are checked without the disassembly submodule.
- [x] Commit source-only room payload `incbin` inventories across Bank03 (34 declarations), Bank0A (75), and Bank1F (157), with pinned-source parser-parity tests for all 266 labelled declarations. The source files provide start-offset and size annotations but no explicit end offsets; computed ends remain unverified.
- [x] Import source exports into project SQLite databases by explicit file path or validated registry name; manifest imports recheck registered format, source revision, and record count before storage. Integration tests round-trip every registered asset through SQLite and the canonical project JSON export.
- [x] Persist validated source-export snapshots in project SQLite databases with explicit v1-to-v2 migration, duplicate-key protection, source provenance, canonical JSON, and SHA-256 integrity checks. This is source metadata persistence, not a semantic game-data schema.
- [~] Commit source-derived metadata inventories with pinned-source parser-parity tests. The current registry contains 29 assets covering:
  - Five seven-entry falling-prize parallel arrays. Pinned-source tests verify
    their shared indexes, and `AddPendantOrCrystal` reads the same selector
    index from each. A local check run reported on 2026-10-28 matched all five
    arrays against the user's ROM at the source-annotated offsets; this is
    evidence for those bytes only, not a trusted ROM-provenance check or CI
    fixture. The repeatable procedure is documented in
    [`docs/real-rom-verification.md`](./docs/real-rom-verification.md).
  - A broader user-run scalar-table cross-check on 2026-10-28 compared 428
    directly numeric entry literals against the same local ROM at the exported
    file offsets and widths: zero mismatches. Another 175 records were skipped
    because their parser literal values were unresolved/non-numeric. In
    particular, `text-dictionary-pointers` (98 entries) and
    `item-receipt-y-offsets` (76 entries) had no directly numeric values, so
    this pass compared no bytes for those assets. This is evidence only for
    the compared values in that local file; skipped records and canonical ROM
    provenance remain unverified. The new `zelda-suite verify-rom-tables`
    command makes this check repeatable and distinguishes full, partial,
    skipped, and failing assets; it has synthetic regression coverage but has
    not yet been re-run by the user against the ROM.
  - 98 text dictionary pointers and 98 pointer-to-fragment metadata records.
  - 397 source text-message labels with offset/length diagnostics.
  - 68 `SpriteActive3_Table` handler entries.
  - Eight `MadBatter_PseudoAttackPlayer_palettes` selector bytes at `$02FB86–$02FB8D`; these are source-derived selector values used by a three-bit lookup index, not decoded color-palette values.
  - 35 music-track pointer expressions and 15 music payload declarations.
  - 128 overworld hidden-item pointer expressions. The pinned source parser
    accounts for 351 three-byte entries plus 67 two-byte sentinels and derives
    all 128 area lists using the runtime's leading-`$FFFF` termination rule.
    The ROM-independent `zelda-suite inspect-overworld-hidden-items` command
    now emits a versioned source-layout report with the raw records, offsets,
    sentinels, area lists, and replacement words. The read-only verifier checks
    550 byte spans; synthetic tests cover matches and mismatches. A user-run
    check against the local ROM is still needed, and value semantics remain
    unresolved. The source report does not establish ROM accuracy.
  - 320 source-indexed `RoomData_ObjectDataPointers` three-byte expressions from `Bank1F.asm`. The `verify-dungeon-room-pointers` command maps all 263 distinct target labels through the three registered source-offset inventories and compares all 320 long pointer values against a local ROM. Source-commented offsets are candidate inputs, not trusted ground truth; the local check, payload bytes, and playable-room count remain open.
  - A companion 320-entry `RoomData_DoorDataPointers` export from the same bank. Its target labels match the object-pointer slots, with 263 distinct labels and 39 empty targets. The regression test checks that all 320 numeric addends are less than the corresponding target label's source-annotated payload size; this bounds-consistency check does not validate those sizes against ROM bytes or decode addend semantics.
  - 266 labelled room payload `incbin` declarations across Bank03, Bank0A, and Bank1F with source start offsets and size annotations; binary payloads and end-offset verification remain unavailable.
  - 164 `Bank0B.asm` plus 84 `Bank0C.asm` overworld High/Low payload declarations.
  - Eight raw `Pool_AddReceiveItem` tables: four 76-entry X/Y/flag/property tables, 76 WRAM target addresses, 76 values, 76 graphics-index bytes, and 14 dungeon masks. The graphics-index table is exported as version 2 with inline comments preserved; its comments omit index `0x40`, so comment IDs are not treated as canonical semantic IDs.
  - A joined `item-receipt-layout` view aligns six 76-entry arrays by their
    positional source index and keeps the 14 dungeon masks separate. It retains
    raw expressions, offsets, and literal values without treating the disputed
    `$40` source-comment gap as a canonical item-ID mapping. The new export
    schema and CLI validator guard count/index/offset alignment; semantic item
    resolution and the user's expanded ROM check remain open.
- [~] Provide read-only ROM image inspection and deterministic file-to-file ROM byte diff/audit output. The diff utility is not yet driven by semantic project edits and is not a ROM writer.
- [x] Add `zelda-suite audit-unresolved-table-expressions` to inventory unresolved expressions in registered scalar-table exports without requiring a ROM. It preserves source expressions and locations, uses conservative syntax classifications only, and never evaluates assembler expressions. A CI integration test pins all 14 registered tables (679 entries: 504 direct numeric, 77 negative decimal, 98 unresolved symbols) to keep extraction coverage visible without claiming ROM verification.
- [x] Provide `zelda-suite verify-rom-tables ROM` to compare numeric literals in registered scalar data-table exports to a headerless 1 MiB local ROM. Reports distinguish pass/partial/skip/fail, use the data directive's byte width separately from the file-offset stride, record a local SHA-256, and never write ROM bytes. Synthetic tests cover matching/mismatching bytes, unresolved expressions, signed decimal literals, strided word tables, report output, and ROM-size rejection. The user's reported real-ROM result (428 compared, 175 skipped, zero mismatches) was from the earlier runbook snippet. The graphics-index table adds 76 direct numeric values; the updated verifier also checks the 76 bounded negative Y-offset literals. The next complete local run is expected to check 580 entries and skip 99 unresolved records, but this expanded result has not yet been run. The updated verifier additionally checks simple negative decimal literals as bounded two's-complement values, including the 76 receive-item Y-offset expressions; rerun it locally to verify those additional bytes. An opt-in format-v2 report classifies skipped raw expressions by syntax shape without evaluating them; default format-v1 output remains unchanged.
- [x] Add `zelda-suite verify-overworld-hidden-items ROM` for source-derived
  pointer, record, sentinel, and replacement-word checks. It recalculates
  label offsets from 3-byte records/2-byte sentinels, compares all 128 pointer
  words plus 351 records, 67 sentinels, and four replacement words, and reports
  sentinel-delimited area groups. Tests use a synthetic ROM built from the
  pinned source; the actual user-supplied ROM comparison and canonical provenance
  checks remain open.
- [x] Add `zelda-suite verify-dungeon-room-pointers ROM` for the 320-entry
  room-object long-pointer table. It compares candidate CPU addresses calculated
  from the three registered payload inventories with three-byte ROM entries,
  includes all 266 payload labels (including three labels unused by the pointer
  table), and preserves the 296/320 playable-room-count discrepancy. Synthetic
  tests validate matching and mismatching pointer bytes; the user's local-ROM
  run, source-offset trust, payload-byte verification, and playable-room set
  remain open.
- [x] Inventory the two overworld High/Low payload banks and validate source-local pairs: 248 declarations form 124 screen tokens (82 in Bank0B and 42 in Bank0C), each with exactly one High and one Low member. The `validate-overworld-payload-pairs` CLI checks this metadata invariant.
- [x] Add `zelda-suite audit-incbin-inventory` to summarize metadata gaps, explicit source-range/size mismatches, and overlaps between candidate spans across all registered incbin inventories. A CI integration test pins the six registered inventories (529 declarations, four metadata gaps, three range/size mismatches, ten candidate overlap pairs) to prevent silent baseline drift. The report is deterministic and source-only; candidate offsets remain unverified until checked against a trusted local ROM.
- [x] Add `zelda-suite audit-text-dictionary` to cross-reference the 98 committed symbolic dictionary pointer entries against all 98 fragment records in CI. It checks source provenance, labels, indexes, entry offsets, and the terminal sentinel; the strict asset loader also rejects inconsistent adjacent fragment offsets and source-extent arithmetic. The known `.You` 2-byte versus 6-byte directive discrepancy remains a warning; pointer values and ROM offsets remain unverified.
- [x] Add `zelda-suite verify-text-dictionary-pointers ROM` to compare the 98 two-byte dictionary pointer entries against source-offset-derived LoROM candidates, with synthetic-ROM match/mismatch tests and a versioned report. The local-ROM run, source-offset trust, fragment-byte verification, ROM provenance, and `Text_DictionaryPointers`/`DictionaryPointers` symbol-name mapping remain open.
- [x] Add `zelda-suite audit-text-message-index` and a CI baseline for the 397 committed message records. It reports six source offset-comment mismatches (three malformed), 38 records without comments in the extra block, and a one-byte extra-block size discrepancy without reading a ROM or decoding messages.
- [x] Add `zelda-suite verify-text-message-bytes ROM` to compare literal message bytes from both pinned source blocks against candidate offsets in a local 1 MiB image. Synthetic tests cover byte matches/mismatches, fail-closed parsing, CLI output, and no-overwrite behavior; a pinned-source test checks all 397 messages and the six offset-comment / one block-size warnings. Actual local-ROM agreement and source-offset/ROM-provenance verification remain open.
- [x] Add a submodule-independent regression baseline for the committed 128-entry `OverworldData_HiddenItems` pointer table. It pins contiguous two-byte slot offsets, the full set of 80 target labels, and the 64-singleton/16-quadruple target distribution; target labels are still source symbols, not verified ROM offsets.
- [ ] Extract and validate the full overworld map, dungeon room, and graphics/palette datasets through YAZE/`z3ed` or independently verified source/ROM parsers.
- [ ] Decode the committed overworld High/Low payloads and establish their relationship to editable map layers. Reconcile all source range/size discrepancies against consumer code and a locally supplied clean US ROM first.
- [ ] Establish complete editable schemas for items/chests/shops, doors/entrances, sprites/placements, message encoding, and audio payloads; distinguish raw metadata from verified semantic meaning.
- [~] Continue documenting source-derived exports, schemas, provenance, regeneration commands, parser limits, and unresolved discrepancies as each asset lands.

**Exit criteria:** Not met. The existing exports are targeted source inventories, not a complete data model for every major game system. Several include targets are absent from the pinned disassembly; no binary payloads are committed, and most source-commented offsets remain unverified against a trusted local ROM. The scalar-table verifier covers registered direct literals and simple in-range negative decimal expressions; symbolic expressions and semantic datasets still require separate checks.

## Phase 2 — Editor Core and Authoring API

**Objective:** Add safe semantic edits to the structured project model.

- [ ] Define CRUD APIs for rooms, chests/items, overworld map elements, entrances, text, and sprite placements.
- [ ] Store semantic game-system records in SQLite with schema migrations, field constraints, and referential integrity. Current source_asset persistence only stores validated source-export snapshots and does not satisfy this item.
- [ ] Map each supported API operation to an explicitly documented ROM write using YAZE/`z3ed` or a direct writer proven against the disassembly.
- [ ] Implement dry-run output, bounds checks, reference checks, and deterministic serialization for every edit.
- [ ] Add a small UI only after the same validated authoring API can serve both human and agent edits.
- [ ] Integrate SpriteSomething ZSPR support and zcompress only after asset round-trip tests exist.

**Exit criteria:** Not met. The current project store is metadata-only; no authoring CRUD API or ROM writer exists yet.

## Phase 3 — Claude Integration and Agent Workflows

**Objective:** Make agent-driven changes structured, reviewable, and reproducible.

- [ ] Expose validated authoring API functions as MCP tools with strict input/output schemas.
- [ ] Select and document an agent harness, session model, tool permissions, and human review boundaries.
- [ ] Require every proposed edit to cite the project record and supporting disassembly label/offset range.
- [ ] Run deterministic ROM diffs and emulator smoke tests for every ROM-changing operation.
- [ ] Demonstrate at least three nontrivial natural-language edit workflows end-to-end.

**Exit criteria:** Not met. The MCP authoring tools and edit-to-build verification loop are future work.

## Phase 4 — Maker-Style Expansion

**Objective:** Enable broad structural changes and complete-game authoring beyond isolated edits.

- [ ] Study Zelda Reloaded Maker's project-file model and record transferable design decisions.
- [ ] Add templates for supported project styles.
- [ ] Add tested bulk operations for overworld generation and entrance/exit graph consistency.
- [ ] Add patch export, reproducible release metadata, generated readmes, and versioned artifacts.
- [ ] Evaluate Solarus or Z3R as optional export targets only after the core project model is stable.

**Exit criteria:** Not met.

## Phase 5 — Hardening and Distribution

**Objective:** Make the suite safe to use, testable, documented, and maintainable.

- [~] Maintain automated regression coverage for source parsers, asset validation, ROM inspection, and byte-diff utilities. CI runs Python syntax checks, Ruff across all `src`/`tests`, strict MyPy on `src`, the full pytest suite, POSIX and Windows setup smoke tests, and a clean wheel build/install smoke test. ROM-dependent verification and golden-ROM round-trip tests remain open until a trusted local ROM and verified writer/build path are available.
- [~] Document current CLI operations, source export formats, and known disassembly/offset caveats; complete API and schema documentation as the subsystems are implemented.
- [x] Provide `scripts/setup.sh` and `scripts/setup.ps1` plus `docs/install.md`; prepare dependencies, initialize and validate a project, refuse to overwrite existing project files, and never fetch or modify a ROM.
- [x] Establish `CHANGELOG.md` and a versioning policy for the package, project JSON format, SQLite schema, asset registry, and individual source-export formats. The release/tag workflow has not yet been exercised.
- [x] Add `CONTRIBUTING.md` guidance for new extractors, schemas, source fixtures, registry/loader updates, and verification evidence.

**Exit criteria:** Not met.

## Guardrails and evidence

- Never commit ROM images or extracted ROM payload bytes. The source export inventories record declarations and metadata only.
- Treat the pinned disassembly revision `347c23f9fc019c72d32da537c9cb235f468d021d` as provenance for the current source exports; do not silently reinterpret or “repair” source comments.
- Before any ROM write is supported, require a verified source/offset mapping, deterministic diff, explicit dry run, and an emulator or equivalent execution check.
- A documented local ROM path is a setup convention, not evidence that a file exists or is a clean/canonical dump. Keep local-ROM checks explicitly marked as unverified until performed against a trusted local file.
- Update this roadmap and the relevant subsystem docs in the same change that alters implementation or changes the verified status of a task.

## Immediate next work

1. Complete ROM provenance validation and external-tool smoke tests. User-run
   local checks on 2026-10-28 matched the five falling-prize arrays and compared
   428 direct numeric scalar-table literals with zero mismatches; 175
   records were skipped by the original snippet, including the 76 signed
   decimal receive-item Y offsets. These checks do not prove canonical ROM
   identity. Rerun `zelda-suite verify-rom-tables`,
   `zelda-suite verify-overworld-hidden-items`, and
   `zelda-suite verify-dungeon-room-pointers` using
   [`docs/real-rom-verification.md`](./docs/real-rom-verification.md).
   On Arch Linux, use the verified generic YAZE release archive, inspect
   `z3ed --help`, then perform only a confirmed read-only ROM operation.
   Keep ROM provenance and the z3cli/model-endpoint gates open until independently
   resolved.
2. Use the new source-only hidden-item layout report to select one small area, then compare its pointer, record bytes, and sentinel grouping against a trusted local ROM. Trace the value-byte consumer before promoting any fields into an editable schema; the source report alone is not ROM verification.
3. Keep Phase 0 local-tool checks visible as blockers; do not treat read-only inspectors as proof that the complete editor pipeline works.
