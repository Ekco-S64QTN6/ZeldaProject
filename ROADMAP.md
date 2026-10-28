# ZeldaProject Roadmap

**Goal:** Build a scriptable, agent-native authoring suite for *The Legend of Zelda: A Link to the Past* (SNES). The long-term target is a structured project model with semantic editing APIs, deterministic ROM builds/diffs, verification, and eventually maker-style authoring.

**Current state (2026-10-27): Phase 1 — Structured Extraction is in progress.** Phase 0 has useful scaffolding but still has environment-dependent verification gates. The repository provides source-derived metadata parsers, a named extracted-asset registry, SQLite project initialization/validation plus schema-v2 storage for validated source-export snapshots, read-only ROM inspection, and file-to-file ROM diff utilities. It does **not** yet provide semantic overworld/dungeon editors or a ROM writer/rebuilder.

Status legend: **[x] verified in repository/automated tests** · **[~] partial; limitations remain** · **[ ] not implemented or not verified in the available environment**.

## Phase 0 — Foundation

**Objective:** Establish the canonical ROM, workspace layout, project format, and low-level access primitives.

- [ ] Verify that a clean US ROM is available locally and is the only base-game ROM used by the build. ROMs are intentionally untracked and are not included in CI.
- [~] Verify header state and document offset mapping. `zelda-suite inspect-rom` reports file size, SHA-256, header-size assessment, and LoROM mapping; its size-based assessment is diagnostic, not proof of a canonical dump or hash.
- [ ] Install and smoke-test YAZE/`z3ed` against the locally supplied US ROM, including actual overworld, dungeon, graphics/palette, and message reads.
- [ ] Test `z3cli` with the chosen model endpoint and a real tool call; decide whether to use it or a thin custom MCP server.
- [x] Choose SQLite as the canonical project format with JSON export, recorded in [ADR 0001](./docs/decisions/0001-project-data-format.md).
- [x] Provide `zelda-suite init`, `validate`, and explicit schema-v1-to-v2 `migrate-project` for a versioned SQLite project plus canonical JSON export. The project can store validated source-export snapshots, but it is not yet the editable game-system data model.

**Exit criteria:** Not met. Local ROM provenance and real YAZE/`z3ed` and agent-harness smoke tests remain outstanding.

## Phase 1 — Structured Extraction (current focus)

**Objective:** Build a source-traceable, queryable metadata model without treating unverified source comments as confirmed ROM facts.

- [x] Add read-only parsers for source pointer tables, Asar `db`/`dw`/`dl` data tables, labelled `incbin` declarations, text dictionary fragments, text message labels, sprite dispatch, and music-track pointers.
- [x] Preserve source inline comments through opt-in `inspect-data-table --include-comments` format v2; the default version-1 export remains backward-compatible and comments are validated as inert strings only.
- [x] Cross-reference the 35-slot music pointer index against the 15 declared payload labels: all 15 payload labels appear in the pointer target set, plus the distinct `Song0B_FairyTheme` target, which has no matching entry in the current `incbin` inventory. The difference is documented but not interpreted as ROM-level absence or pointer resolution.
- [x] Add versioned JSON export validation and a manifest-backed named-asset loader that checks registered names, safe filenames, format, source revision, and record count.
- [x] Commit the source-only 320-entry dungeon room pointer table with pinned-source parser-parity coverage; do not treat its count as the number of playable rooms or as resolved ROM targets.
- [x] Cross-reference the 320 dungeon pointer slots with all three payload inventories and pinned Bank03/Bank0A/Bank1F source labels: the inventories cover all 266 definitions, all 263 distinct pointer target labels are included, and exactly three definitions are not referenced by the table. This remains source-symbol verification, not ROM pointer resolution.
- [x] Commit source-only room payload `incbin` inventories across Bank03 (34 declarations), Bank0A (75), and Bank1F (157), with pinned-source parser-parity tests for all 266 labelled declarations. The source files provide start-offset and size annotations but no explicit end offsets; computed ends remain unverified.
- [x] Import source exports into project SQLite databases by explicit file path or validated registry name; manifest imports recheck registered format, source revision, and record count before storage. Integration tests round-trip every registered asset through SQLite and the canonical project JSON export.
- [x] Persist validated source-export snapshots in project SQLite databases with explicit v1-to-v2 migration, duplicate-key protection, source provenance, canonical JSON, and SHA-256 integrity checks. This is source metadata persistence, not a semantic game-data schema.
- [~] Commit source-derived metadata inventories with pinned-source parser-parity tests. The current registry contains 25 assets covering:
  - Five seven-entry falling-prize parallel arrays.
  - 98 text dictionary pointers and 98 pointer-to-fragment metadata records.
  - 397 source text-message labels with offset/length diagnostics.
  - 68 `SpriteActive3_Table` handler entries.
  - 35 music-track pointer expressions and 15 music payload declarations.
  - 128 overworld hidden-item pointer expressions.
  - 320 source-indexed `RoomData_ObjectDataPointers` three-byte expressions from `Bank1F.asm`; usable-room count and target resolution remain unverified.
  - 266 labelled room payload `incbin` declarations across Bank03, Bank0A, and Bank1F with source start offsets and size annotations; binary payloads and end-offset verification remain unavailable.
  - 164 `Bank0B.asm` plus 84 `Bank0C.asm` overworld High/Low payload declarations.
  - Seven raw `Pool_AddReceiveItem` arrays: four 76-entry X/Y/flag/property tables, 76 WRAM target addresses, 76 values, and 14 dungeon masks.
- [~] Provide read-only ROM image inspection and deterministic file-to-file ROM byte diff/audit output. The diff utility is not yet driven by semantic project edits and is not a ROM writer.
- [x] Inventory the two overworld High/Low payload banks and validate source-local pairs: 248 declarations form 124 screen tokens (82 in Bank0B and 42 in Bank0C), each with exactly one High and one Low member. The `validate-overworld-payload-pairs` CLI checks this metadata invariant.
- [ ] Extract and validate the full overworld map, dungeon room, and graphics/palette datasets through YAZE/`z3ed` or independently verified source/ROM parsers.
- [ ] Decode the committed overworld High/Low payloads and establish their relationship to editable map layers. Reconcile all source range/size discrepancies against consumer code and a locally supplied clean US ROM first.
- [ ] Establish complete editable schemas for items/chests/shops, doors/entrances, sprites/placements, message encoding, and audio payloads; distinguish raw metadata from verified semantic meaning.
- [~] Continue documenting source-derived exports, schemas, provenance, regeneration commands, parser limits, and unresolved discrepancies as each asset lands.

**Exit criteria:** Not met. The existing exports are targeted source inventories, not a complete data model for every major game system. Several include targets are absent from the pinned disassembly; no binary payloads are committed, and source-commented offsets are not independently verified against a local ROM.

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

- [~] Add automated regression tests for source parsers, asset validation, ROM inspection, and byte-diff utilities; golden-ROM round-trip tests are not possible until a verified writer/build path exists.
- [~] Document current CLI operations, source export formats, and known disassembly/offset caveats; complete API and schema documentation as the subsystems are implemented.
- [ ] Provide an installer that prepares dependencies and initializes the workspace without fetching or distributing copyrighted ROM files.
- [ ] Establish a changelog and semantic versioning for both project and exported asset formats.
- [x] Add `CONTRIBUTING.md` guidance for new extractors, schemas, source fixtures, registry/loader updates, and verification evidence.

**Exit criteria:** Not met.

## Guardrails and evidence

- Never commit ROM images or extracted ROM payload bytes. The source export inventories record declarations and metadata only.
- Treat the pinned disassembly revision `347c23f9fc019c72d32da537c9cb235f468d021d` as provenance for the current source exports; do not silently reinterpret or “repair” source comments.
- Before any ROM write is supported, require a verified source/offset mapping, deterministic diff, explicit dry run, and an emulator or equivalent execution check.
- Keep local-ROM checks explicitly marked as unverified until performed against a trusted local file.
- Update this roadmap and the relevant subsystem docs in the same change that alters implementation or changes the verified status of a task.

## Immediate next work

1. Use a locally supplied clean US ROM and source consumers to resolve the known source annotation issues without changing the source export facts.
2. Decode one small, well-understood source-data area end-to-end before expanding the editable project schema.
3. Keep Phase 0 local-tool checks visible as blockers; do not treat read-only inspectors as proof that the complete editor pipeline works.
