# ZeldaProject Roadmap

**Goal:** Build a scriptable, agent-native authoring suite for *The Legend of Zelda: A Link to the Past* (SNES). The long-term target is a structured project model with semantic editing APIs, deterministic ROM builds/diffs, verification, and eventually maker-style authoring.

**Current state (2026-10-30): Phase 1 — Structured Extraction is in progress, with two bounded semantic editing slices in Phase 2.** The user's local US ROM matches the documented No-Intro USA fingerprint and the user confirms it boots. A user-run YAZE v0.7.2 `z3ed` smoke test verified several read-only ROM, dungeon, graphics/palette, and message commands; the overworld-map command still fails on screen 80 with an out-of-range offset, and `z3cli` remains untested. The repository provides source-derived metadata parsers, a named extracted-asset registry, SQLite project storage with schema-v5 migrations whose individual DDL transitions use explicit SQLite transactions, plus source-preserving semantic models for overworld hidden items and packed dungeon chest records. Broader room/map authoring, ROM writing/rebuilding, and full emulator/tool integration are not implemented.

Status legend: **[x] verified in repository/automated tests** · **[~] partial; limitations remain** · **[ ] not implemented or not verified in the available environment**.

## Phase 0 — Foundation

**Objective:** Establish the canonical ROM, workspace layout, project format, and low-level access primitives.

- [~] Confirm local US-ROM identity and bootability. On 2026-10-29 the user-run file matched the documented No-Intro USA size, CRC-32, SHA-1, and MD5 fingerprints and the user confirmed it boots. This supports byte identity with that catalog entry plus a manual boot check; it does not independently establish chain of custody or provide an automated emulator test. ROMs remain untracked and are excluded from CI; see [the local-ROM verification runbook](./docs/real-rom-verification.md).
- [~] Verify header state and document offset mapping. `zelda-suite inspect-rom` reports file size, SHA-256, header-size assessment, and LoROM mapping; its size-based assessment is diagnostic, not proof of a canonical dump or hash.
- [~] Smoke-test YAZE v0.7.2 `z3ed` against the locally supplied US ROM. ROM identification, raw reads, dungeon room/sprite inspection, hex reads, overworld/dungeon palette reads, and message list/search succeeded. `overworld-describe-map --screen=80` fails with `Offset 1311049 out of range (size: 1048576)`; a source audit traced this to v0.7.2's unconditional `LoadDiggableTiles()` read of ZSCustomOverworld v3 settings address `0x140149`, not to a screen-80 pointer. The malformed staircase label is also source-diagnosed: v0.7.2 stores `absl::StrCat(...).data()` from a temporary string into a `const char*` field; its pointer lifetime ends before CLI serialization. Upstream corrected these issues in commits [`566d7c6`](https://github.com/scawful/yaze/commit/566d7c6ea08b0df2addbb67940aa56794ef052fb) (2026-09-29) and [`8d4f1ad`](https://github.com/scawful/yaze/commit/8d4f1ad59f539f378ca63faa84545b59e3aa3c5b) (2026-10-13). The user's v0.7.2 binary has not been retested with an updated build. See [`docs/real-rom-verification.md`](./docs/real-rom-verification.md).
- [~] Provide an opt-in project-bound stdio MCP server for bounded project reads/validation and dry-run-first custom hidden-item create/update/delete. The z3cli/model endpoint and a real external host session remain unverified.
- [x] Choose SQLite as the canonical project format with JSON export, recorded in the accepted [ADR 0001](./docs/decisions/0001-project-data-format.md).
- [x] Provide `zelda-suite init`, `validate`, and explicit schema-v1-to-v5 `migrate-project` for a versioned SQLite project plus canonical JSON export. Schema v5 stores source-preserving overworld hidden-item areas/records, separate project-authored hidden-item additions with many-to-many area links, and packed dungeon chest records with constrained field edits; it is not yet a general game-system data model.

**Exit criteria:** Not met. The local image matches the published reference fingerprint and the user reports a successful boot. Partial YAZE/`z3ed` read-only access is verified. The v0.7.2 map-read failure is source-diagnosed as an out-of-range ZSCustomOverworld v3 setting read during global initialization, and the malformed staircase label is source-diagnosed as a dangling pointer to a temporary string. Upstream corrections exist for both; an updated-binary runtime retest, z3cli/model-endpoint, and automated emulator smoke tests remain outstanding.

## Phase 1 — Structured Extraction (current focus)

**Objective:** Build a source-traceable, queryable metadata model without treating unverified source comments as confirmed ROM facts.

- [x] Add read-only parsers for source pointer tables, Asar `db`/`dw`/`dl` data tables, labelled `incbin` declarations, text dictionary fragments, text message labels, sprite dispatch, and music-track pointers. CI also pins the committed 68-entry `SpriteActive3_Table` export when the disassembly submodule is absent, including contiguous `$79–$BC` slots and its six handler alias groups; handler address comments remain source annotations.
- [x] Fail closed when a requested pointer-table label appears more than once in the source; the parser reports every matching source line rather than silently selecting the first matching block.
- [x] Fail closed when a scoped data-table parent label appears more than once; report every matching declaration line instead of silently parsing the first block. A synthetic regression test covers duplicate global parent labels.
- [x] Add a mixed-width `db`/`dw`/`dl` source-table parser/export with byte-accurate field offsets; pin the two-row `Landmine_Draw_OAM_groups` fixture without decoding OAM semantics or claiming ROM verification.
- [x] Register all 168 packed `Dungeon_ChestData` records from `Bank01.asm`, preserving raw 24-bit values and exposing the source-commented top-byte item value, low-15-bit room value, and bit-15 big-chest flag. Add `inspect-dungeon-chest-data` and `audit-dungeon-chest-data`, source-parity/consumer tests, and schemas; range offsets and item-name mappings remain unverified.
- [x] Add `audit-dungeon-chest-room-references` to join the 168 chest records to matching object/door pointer slots using the pinned consumer relationship (`$A0` room value and `$A0 * 3` pointer index). The current inventory has 168/168 slot matches, 106 distinct room values, 32 repeated-room groups, and no object/door target-label mismatches. This is source-level cross-reference evidence only; ROM offsets and payload bytes remain unverified, item names stay raw, and the playable-room set is unresolved.
- [x] Register seven `Sprite_ShopKeeper` purchase handlers, preserving their source-coded A/Y price bytes and receipt selector indexes. Add `inspect-shop-item-handlers` plus `audit-shop-item-handlers` to join the seven receipt indexes to the raw 76-slot receive-item layout. Receipt indices are positional, not canonical item IDs; handler annotations and price behavior are not ROM/runtime verified, and room-specific shop stock remains open.
- [x] Register the green, blue, and red potion-shop transactions from `sprite_potion_shop.asm`, preserving source compare/deduction literals 60/160/120, empty-bottle check lines, and receipt indexes `$2F/$30/$2E`. Add `inspect-potion-shop-transactions` and `audit-potion-shop-transactions` to join the three receipt indexes to raw receive-item slots and graphics-comment annotations; runtime price behavior, semantic item identities, and room-specific stock remain unverified.
- [x] Register three additional source-coded shop transactions: Bomb Shop Bomb (100 rupees, receipt slot `$28`), Bomb Shop Super Bomb (100 rupees, persistent flag plus tagalong reward rather than a receipt selector), and Bottle Vendor bottle sale (100 rupees, receipt selector `$16`). Add a strict source export and audit joining the two selectors to raw receive-item slots and graphics-comment annotations; runtime price/reward behavior, semantic item identities, and room-specific stock remain unverified.
- [x] Audit the 76 inline comments on `.item_graphics_indices` independently of the dense table indexes. Preserve source-comment IDs and labels, report the missing `$40` annotation and the 12 `$41–$4C` comments attached to table slots `$40–$4B`, and carry those raw annotations into the shop audit without treating them as canonical item IDs.
- [x] Register seven source-derived non-shop paid overworld interactions across six pinned sprite files: Fortune Teller price-table readings (10/15/20/30), Digging Game entry (80), Zora King Flippers (500), Kiki fees (10/100), Archery Game (20), and Lake Hylia Fairy donations (5/20/25/50). Add a strict source parser/export and `audit-paid-overworld-interactions`; preserve the Digging Game reward dispatch/pool and separate heart-piece gate without claiming runtime probabilities or verified ROM offsets.
- [x] Export the 243 source-commented `SpritePrep_Main` dispatch entries, preserving handler expressions, address annotations, descriptions and wrapped comments while leaving the inline-table file offset unset. Add `zelda-suite audit-sprite-prep-dispatch` to cross-reference its IDs with `SpriteActive3_Table`; the 68 shared IDs show index coverage only, not equivalent handler semantics or verified ROM addresses.
- [x] Register the 54-word `Pool_OAM_GetBufferPosition` table and `zelda-suite audit-oam-allocation` structured report. The audit groups six region upper limits with 48 fallback points (eight per A–F region) and tests the source lookup's selector/counter arithmetic; source-commented offsets and runtime OAM positions remain unverified.
- [x] Export the eight-entry `MadBatter_PseudoAttackPlayer_palettes` selector table from pinned `Sprites/sprite_mad_batter.asm`; its source-parity test preserves literal selector bytes and the source-commented `$02FB86–$02FB8D` range without claiming color-palette decoding or ROM verification.
- [x] Export the two-entry `Sprite_CrystalSwitch_palettes` selector table from pinned `Sprites/sprite_crystal_switch.asm` and test its bit-indexed consumer in `Sprites/sprite_prep.asm`; the source-commented `$0338CE–$0338CF` range and selector values are not decoded colors or ROM-verified bytes.
- [x] Export the eight raw 16-bit `CrystalMaiden_Configure_palette` words from pinned `Sprites/sprite_crystal_maiden.asm`; retain the `$0F4CD3–$0F4CE2` source-commented range and explicitly leave the routine's `.palette` versus top-level label relationship unresolved.
- [x] Export the nine `CrystalMaiden_ShowMessage_message_ids` words from pinned `Sprites/sprite_crystal_maiden.asm` at source-commented `$0F4EBC–$0F4ECD` and cross-reference each unique ID against the registered 397-message index. Keep the relationship to the routine's local `.message_ids` label unresolved; no ROM byte verification is claimed.
- [x] Preserve source inline comments through opt-in `inspect-data-table --include-comments` format v2; the default version-1 export remains backward-compatible and comments are validated as inert strings only.
- [x] Cross-reference the 35-slot music pointer index against the 15 declared payload labels: all 15 payload labels appear in the pointer target set, plus the distinct `Song0B_FairyTheme` target, which has no matching entry in the current `incbin` inventory. The `zelda-suite audit-music-assets` API/CLI now reports that unmatched label and the three auxiliary declarations without size annotations; these remain source metadata findings, not ROM-level payload absence or pointer resolution.
- [x] Add versioned JSON export validation and a manifest-backed named-asset loader that checks registered names, safe filenames, format, source revision, and record count. A registry-wide regression test also requires all 39 committed exports to use canonical sorted JSON, unchanged array ordering, strict JSON values, and a final newline.
- [x] Commit the source-only 320-entry dungeon room pointer table with pinned-source parser-parity coverage; do not treat its count as the number of playable rooms or as resolved ROM targets.
- [x] Commit the companion 320-entry `RoomData_DoorDataPointers` export at source-commented offset `$0F83C0`; preserve its numeric addends and pin all target labels against the matching `RoomData_ObjectDataPointers` slots. Addend meaning and local-ROM verification remain open.
- [x] Add `audit-dungeon-room-door-pointers` to report the 320 door-pointer addends, check slot-for-slot target-label alignment with the object-pointer table, and compare each numeric addend to the target's source-declared size. The pinned inventory has 320/320 in-range addends and zero slot mismatches; these checks do not verify the declared sizes, target offsets, door semantics, or playable-room count against a ROM.
- [x] Cross-reference the 320 dungeon pointer slots with all three payload inventories and pinned Bank03/Bank0A/Bank1F source labels: the inventories cover all 266 definitions, all 263 distinct pointer target labels are included, and exactly three definitions are not referenced by the table. This remains source-symbol verification, not ROM pointer resolution. Add the source-only `zelda-suite audit-dungeon-room-assets` command and CI baseline so the committed JSON relationships are checked without the disassembly submodule.
- [x] Commit source-only room payload `incbin` inventories across Bank03 (34 declarations), Bank0A (75), and Bank1F (157), with pinned-source parser-parity tests for all 266 labelled declarations. The source files provide start-offset and size annotations but no explicit end offsets; computed ends remain unverified.
- [x] Import source exports into project SQLite databases by explicit file path or validated registry name; manifest imports recheck registered format, source revision, and record count before storage. Integration tests round-trip every registered asset through SQLite and the canonical project JSON export.
- [x] Persist validated source-export snapshots in project SQLite databases with explicit v1-to-v2 migration, duplicate-key protection, source provenance, canonical JSON, and SHA-256 integrity checks. This is source metadata persistence, not a semantic game-data schema.
- [~] Commit source-derived metadata inventories with pinned-source parser-parity tests. The current registry contains 40 assets covering:
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
  - 243 `SpritePrep_Main` preparation-dispatch entries for sprite IDs `$00–$F2`; the inline table offset is not established by a source comment, and handler addresses are retained as annotations only.
  - 68 `SpriteActive3_Table` handler entries, all within the prep-table ID range. A source-only audit checks the 68 shared IDs, but does not assert that the two handler tables have equivalent runtime behavior.
  - 168 packed `Dungeon_ChestData` records. The audit reports 106 raw room values, 32 room values with multiple entries, 11 entries with the big-chest flag, and 33 distinct raw item values. Item-name mappings and source-range offsets remain unverified.
  - Seven standard-shopkeeper purchase handlers, with source-coded prices of 150, 50, 500, 10, 30, 50, and 10 and receipt selector slots 46, 4, 5, 66, 68, 49, and 14. The audit joins these positional selectors to the existing receive-item layout but does not resolve item names, prove price behavior in a running ROM, or map handlers to room-specific shop stock.
  - Three special-shop transactions at 100 rupees each: Bomb Shop Bomb (receipt slot `$28`), Bomb Shop Super Bomb (state flag/tagalong reward, no receipt slot), and Bottle Vendor Bottle Sale (receipt selector `$16`). The two receipt selectors are cross-referenced by dense index with raw receipt fields and source-comment annotations; runtime reward behavior, canonical item IDs, and room-specific stock remain open.
  - Seven non-shop paid overworld interactions across six source files, with fixed and variable price models, plus the Digging Game’s raw reward dispatch/pool and heart-piece gate. Fee behavior and reward probabilities remain source-only and unverified against ROM execution.
  - Eight `MadBatter_PseudoAttackPlayer_palettes` selector bytes at `$02FB86–$02FB8D`; these are source-derived selector values used by a three-bit lookup index, not decoded color-palette values.
  - Two `Sprite_CrystalSwitch_palettes` selector bytes at `$0338CE–$0338CF`, used by a one-bit lookup in the Crystal Switch prep routine; these are not decoded color-palette values.
  - Eight raw 16-bit `CrystalMaiden_Configure_palette` words at `$0F4CD3–$0F4CE2`; the adjacent routine's `.palette` reference is not asserted to resolve to the top-level data label, and the words are not rendered RGB values.
  - Nine `CrystalMaiden_ShowMessage_message_ids` words at `$0F4EBC–$0F4ECD`; their eight distinct IDs exist in the registered text-message index, but the local `.message_ids`/global-label relationship remains unresolved.
  - Two `Landmine_Draw_OAM_groups` rows at source-commented `$0E80FC–$0E810B`; the parser preserves mixed `dw`/`db` field widths and byte offsets, but does not assign OAM meaning.
  - 35 music-track pointer expressions and 15 music payload declarations.
  - 128 overworld hidden-item pointer expressions. The pinned source parser
    accounts for 351 three-byte entries plus 67 two-byte sentinels and derives
    all 128 area lists using the runtime's leading-`$FFFF` termination rule.
    The ROM-independent `zelda-suite inspect-overworld-hidden-items` command
    emits a versioned layout report, and `audit-overworld-hidden-item-value-semantics`
    traces the third byte through the pinned `Overworld_RevealSecret` consumer:
    325 ordinary mask values and 26 extended selectors using low-nibble byte
    offsets into the four-word `Overworld_SecretTileType` table. This is source
    consumer evidence only; canonical item IDs and decoded map semantics remain
    unresolved. The read-only verifier checks 550 byte spans; the user's
    2026-10-29 local run matched all of them and the image fingerprint matched
    the cited USA entry.
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
- [x] Add `zelda-suite audit-unresolved-table-expressions` to inventory unresolved expressions in registered scalar-table exports without requiring a ROM. It preserves source expressions and locations, uses conservative syntax classifications only, and never evaluates assembler expressions. A CI integration test pins all 19 registered tables (760 entries: 585 direct numeric, 77 negative decimal, 98 unresolved symbols) to keep extraction coverage visible without claiming ROM verification.
- [x] Provide `zelda-suite verify-rom-tables ROM` to compare numeric literals in registered scalar data-table exports to a headerless 1 MiB local ROM. Reports distinguish pass/partial/skip/fail, use the data directive's byte width separately from the file-offset stride, record a local SHA-256, and never write ROM bytes. Synthetic tests cover matching/mismatching bytes, unresolved expressions, signed decimal literals, strided word tables, report output, and ROM-size rejection. The user's 2026-10-29 complete run compared 662 numeric values with zero mismatches and left 98 symbolic expressions unresolved. The verifier checks simple negative decimal literals as bounded two's-complement values, including the 76 receive-item Y-offset expressions; synthetic tests cover this behavior. The latest local count is recorded evidence for this image, not a semantic resolution of skipped expressions. An opt-in format-v2 report classifies skipped raw expressions by syntax shape without evaluating them; default format-v1 output remains unchanged.
- [x] Add `zelda-suite verify-overworld-hidden-items ROM` for source-derived
  pointer, record, sentinel, and replacement-word checks. It recalculates
  label offsets from 3-byte records/2-byte sentinels, compares all 128 pointer
  words plus 351 records, 67 sentinels, and four replacement words, and reports
  sentinel-delimited area groups. Tests use a synthetic ROM built from the
  pinned source; the user's local run matched all 550 spans and the image
  fingerprint matched the cited USA entry. Canonical item IDs and decoded map
  semantics remain unresolved.
- [x] Add `zelda-suite verify-dungeon-room-pointers ROM` for the 320-entry
  room-object long-pointer table. It compares candidate CPU addresses calculated
  from the three registered payload inventories with three-byte ROM entries,
  includes all 266 payload labels (including three labels unused by the pointer
  table), and preserves the 296/320 playable-room-count discrepancy. Synthetic
  tests validate matching and mismatching pointer bytes; the user's local ROM
  matched all 320 pointer entries. Source-offset findings, room payload bytes,
  and the playable-room set remain open.
- [x] Inventory the two overworld High/Low payload banks and validate source-local pairs: 248 declarations form 124 screen tokens (82 in Bank0B and 42 in Bank0C), each with exactly one High and one Low member. The `validate-overworld-payload-pairs` CLI checks this metadata invariant.
- [x] Add `audit-overworld-payload-layout` to join all 124 High/Low pairs and expose each declaration's source line, include path, declared size, annotated start/end, calculated end, range-size status, and candidate High/Low adjacency. The report is pinned to disassembly revision `347c23f9fc019c72d32da537c9cb235f468d021d` and the 82/42 Bank0B/Bank0C pair counts because its source-log/consumer line references and version-1 schema depend on that baseline. It pins 244 range-size matches, three mismatches, and one missing/unparseable range while explicitly leaving payload decoding and trusted-ROM offset checks open.
- [x] Add `zelda-suite audit-incbin-inventory` to summarize metadata gaps, explicit source-range/size mismatches, and overlaps between candidate spans across all registered incbin inventories. A CI integration test pins the six registered inventories (529 declarations, four metadata gaps, three range/size mismatches, ten candidate overlap pairs) to prevent silent baseline drift. The report is deterministic and source-only; candidate offsets remain unverified until checked against a trusted local ROM.
- [x] Add `zelda-suite audit-text-dictionary` to cross-reference the 98 committed symbolic dictionary pointer entries against all 98 fragment records in CI. It checks source provenance, labels, indexes, entry offsets, and the terminal sentinel; the strict asset loader also rejects inconsistent adjacent fragment offsets and source-extent arithmetic. The known `.You` two-byte comment extent versus six-byte `dw` directive is a warning; a source test now pins the mismatch and preserves both facts.
- [x] Add `zelda-suite verify-text-dictionary-pointers ROM` to compare the 98 two-byte dictionary pointer entries against source-commented fragment starts and an explicit exclusive-end candidate for the terminal pointer, with synthetic-ROM match/mismatch tests and a versioned report. The local-ROM pointer-word re-run matched all 98 entries. A source audit now confirms that the consumer references `Text_DictionaryPointers` at Bank0E.asm:6018–6019 while the only declared table is `DictionaryPointers` at line 6039, with no explicit alias in the pinned file. Source-offset trust, fragment-byte verification, and symbol mapping remain open; the fingerprint and manual boot evidence are recorded under Phase 0.
- [x] Add `zelda-suite audit-text-message-index` and a CI baseline for the 397 committed message records. It reports six source offset-comment mismatches (three malformed), 38 records without comments in the extra block, and a one-byte extra-block size discrepancy without reading a ROM or decoding messages.
- [x] Add `zelda-suite verify-text-message-bytes ROM` to compare literal message bytes from both pinned source blocks against candidate offsets in a local 1 MiB image. Synthetic tests cover byte matches/mismatches, fail-closed parsing, CLI output, and no-overwrite behavior; a pinned-source test checks all 397 messages and the six offset-comment / one block-size warnings. The user's local-ROM run matched the checked message bytes. Source-offset trust and message decoding remain open; the image fingerprint matched the cited USA catalog entry.
- [x] Add a submodule-independent regression baseline for the committed 128-entry `OverworldData_HiddenItems` pointer table. It pins contiguous two-byte slot offsets, the full set of 80 target labels, and the 64-singleton/16-quadruple target distribution; target labels are still source symbols, not verified ROM offsets.
- [ ] Extract and validate the full overworld map, dungeon room, and graphics/palette datasets through YAZE/`z3ed` or independently verified source/ROM parsers. The Landmine field export, OAM allocator audit and prep-dispatch inventory are bounded source inventories, not the complete sprite/graphics dataset.
- [ ] Decode the committed overworld High/Low payloads into editable map layers from the actual `bin/ow/*.bin` data or a trusted local ROM. Source research now documents the Map32 high-byte/low-byte relationship and audits all current comment discrepancies, but the referenced payload files are absent from the pinned tree and their offsets still require trusted-ROM verification.
- [ ] Establish complete editable schemas for items/chests/shops, doors/entrances, sprites/placements, message encoding, and audio payloads; distinguish raw metadata from verified semantic meaning. The packed chest inventory, purchase-handler catalogs, the special-shop transaction catalog, paid-overworld interaction inventory, and receive-item comment audit are bounded source evidence, not a complete editable item/chest/shop model.
- [~] Continue documenting source-derived exports, schemas, provenance, regeneration commands, parser limits, and unresolved discrepancies as each asset lands.

**Exit criteria:** Not met. The existing exports are targeted source inventories, not a complete data model for every major game system. Several include targets are absent from the pinned disassembly; no binary payloads are committed, and most source-commented offsets remain unverified against a trusted local ROM. The scalar-table verifier covers registered direct literals and simple in-range negative decimal expressions; symbolic expressions and semantic datasets still require separate checks.

## Phase 2 — Editor Core and Authoring API

**Objective:** Add safe semantic edits to the structured project model.

- [~] Begin semantic CRUD APIs with source-preserving overworld hidden-item reads/updates and packed dungeon chest field edits in schema v5. Project-authored hidden-item records support dry-run-first create/update/delete with many-to-many area assignments and bounded coordinate/value edits. Imported hidden-item and dungeon-chest updates now also return read-only before/proposed previews by default; CLI `--apply` or Python `dry_run=False` is required to persist, with regression tests for no-write and apply paths. The 351 imported source rows, baselines, and source alias relationships remain unchanged. General room/map editing and all ROM writes remain future work.
- [~] Store semantic game-system records in SQLite schema v5 with migrations, field bounds, packed-value checks, and foreign-key area/record relationships. Other domains remain source_asset snapshots until their schemas are implemented.
- [x] Make overworld hidden-item and dungeon chest semantic-model imports preview-first by default. Synthetic regression tests verify proposed metadata/counts, replacement previews, and byte-for-byte preservation of SQLite plus the JSON sidecar; CLI `--apply` / Python `dry_run=False` are the only persistence paths.
- [x] Add a project-facing read-only audit that joins the editable chest model's current room values to the pinned object/door pointer inventories, retaining source room baselines and edit status. Regression coverage verifies clean joins, edited in-range and out-of-range room values, mismatched object/door target labels, missing models, CLI failure behavior, and no-overwrite report output. Candidate offsets and ROM bytes remain unverified; the command does not read or write ROM bytes.
- [ ] Map each supported API operation to an explicitly documented ROM write using YAZE/`z3ed` or a direct writer proven against the disassembly.
- [~] Implement dry-run output, bounds checks, reference checks, and deterministic serialization for every edit. Imported hidden-item/chest updates and project-authored hidden-item CRUD are preview-first; `migrate-project --dry-run` simulates all schema transitions on a disposable SQLite backup; source-asset imports offer `--dry-run` previews for explicit-path and manifest-backed imports, including replacements. Both overworld hidden-item and dungeon chest semantic-model imports now also preview by default; CLI `--apply` or Python `dry_run=False` is required to persist, and replacement previews expose the prior model before resetting imported edits. Other future write surfaces still need review against this contract.
- [ ] Add a small UI only after the same validated authoring API can serve both human and agent edits.
- [ ] Integrate SpriteSomething ZSPR support and zcompress only after asset round-trip tests exist.

**Exit criteria:** Not met. Schema v5 supports bounded source-row edits, dry-run-first project-authored hidden-item create/update/delete, and packed dungeon chest field edits. General room/map editing, dry-run ROM writes, and a ROM writer remain future work.

## Phase 3 — Claude Integration and Agent Workflows

**Objective:** Make agent-driven changes structured, reviewable, and reproducible.

- [~] Expose project validation/source metadata reads, bounded overworld/dungeon
  reads, a read-only chest-to-room-pointer audit, full/single/raw-field-filtered
  chest reads, and AND-filtered overworld hidden-item searches across imported
  and project-authored records. The optional stdio MCP server also exposes
  dry-run-first project-authored hidden-item CRUD and preview-first packed
  dungeon-chest/imported-overworld updates. Strict schemas pin record/field
  ranges; edits preserve immutable source baselines and area aliases. Source
  imports and ROM reads/writes remain outside the tool surface.
- [~] Document the one-project-per-process session model, read/write tool
  permission groups, and explicit human-approval gate in
  [docs/agent-workflows.md](./docs/agent-workflows.md). The host-neutral
  reference procedure is documented, but selection/configuration of a concrete
  MCP host and live interoperability are not verified.
- [ ] Require every proposed edit to cite the project record and supporting disassembly label/offset range.
- [ ] Run deterministic ROM diffs and emulator smoke tests for every ROM-changing operation.
- [ ] Demonstrate at least three nontrivial natural-language edit workflows end-to-end.

**Exit criteria:** Not met. The bounded MCP surface and host-neutral approval
procedure are documented, but a concrete host/session, live interoperability,
three completed natural-language workflows, deterministic ROM diffs, and
emulator-backed edit-to-build verification remain future work.

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
- [~] Make each schema-v1-to-v5 migration step transactional: acquire a SQLite write reservation with `BEGIN IMMEDIATE` before DDL, then commit table creation and matching version metadata together. A synthetic mid-DDL failure test proves the v4-to-v5 custom-table step rolls back without partial tables; earlier committed steps in a multi-version upgrade remain intact.
- [~] Document current CLI operations, source export formats, and known disassembly/offset caveats; complete API and schema documentation as the subsystems are implemented.
- [x] Provide `scripts/setup.sh` and `scripts/setup.ps1` plus `docs/install.md`; prepare dependencies, initialize and validate a project, refuse to overwrite existing project files, and never fetch or modify a ROM.
- [x] Establish `CHANGELOG.md` and a versioning policy for the package, project JSON format, SQLite schema, asset registry, and individual source-export formats. The release/tag workflow has not yet been exercised.
- [x] Add `CONTRIBUTING.md` guidance for new extractors, schemas, source fixtures, registry/loader updates, and verification evidence.

**Exit criteria:** Not met.

## Guardrails and evidence

- Never commit ROM images or extracted ROM payload bytes. The source export inventories record declarations and metadata only.
- Treat the pinned disassembly revision `347c23f9fc019c72d32da537c9cb235f468d021d` as provenance for the current source exports; do not silently reinterpret or “repair” source comments.
- Before any ROM write is supported, require a verified source/offset mapping, deterministic diff, explicit dry run, and an emulator or equivalent execution check.
- A documented local ROM path is a setup convention, not proof that a file exists. The user's supplied image matches the published No-Intro USA fingerprint and the user reports a successful boot, but do not generalize this evidence to a different file or treat it as independent chain-of-custody proof.
- Update this roadmap and the relevant subsystem docs in the same change that alters implementation or changes the verified status of a task.

## Immediate next work

1. Re-test the read-only YAZE map command with an updated upstream build,
   then exercise the separate z3cli/model-endpoint path. The user's official
   v0.7.2 Linux archive passed several reads, but
   `overworld-describe-map --screen=80` failed with
   `Offset 1311049 out of range (size: 1048576)`. The 2026-10-30 source audit
   found that v0.7.2 unconditionally reads `0x140149` in
   `Overworld::LoadDiggableTiles()`; the constant is ZSCustomOverworld v3
   settings storage and lies outside this 1 MiB ROM. This is a global load
   failure, not evidence of a screen-80 pointer defect. Upstream commit
   [`566d7c6`](https://github.com/scawful/yaze/commit/566d7c6ea08b0df2addbb67940aa56794ef052fb)
   (2026-09-29) removed that invalid read. The staircase label issue is a
   separate lifetime bug: v0.7.2 stores a pointer from a temporary
   `absl::StrCat()` string in the public `const char*` staircase record.
   Upstream commit
   [`8d4f1ad`](https://github.com/scawful/yaze/commit/8d4f1ad59f539f378ca63faa84545b59e3aa3c5b)
   (2026-10-13) gives those labels stable storage and adds a lifetime
   regression test. Retest a build containing both corrections before
   claiming map or staircase output support. Preserve the user's before/after ROM SHA-256
   (`66871d66be19ad2c34c927d6b14cd8eb6fc3181965b6e517cb361f7316009cfb`)
   when repeating read-only checks. Do not issue write commands.
   `z3cli` remains untested with a model endpoint.
2. [~] Reconcile the six dungeon-room source-comment offsets. The pinned
   source-order candidates are now bracketed by adjacent declaration arithmetic:
   the previous declaration's commented start plus its `Size:` equals each
   candidate, and the current payload size reaches the next declaration's
   commented start. The six original comments remain preserved and visible as
   findings; a regression test pins all six boundaries. This resolves the
   source-order inconsistency but does not verify room payload bytes or prove
   candidate ROM offsets canonical. See the boundary table in
   [the ROM verification runbook](./docs/real-rom-verification.md).
   The dictionary terminal pointer matches exclusive-end candidate `$C8D9`,
   calculated from the inclusive DATA-range comment. The pinned consumer reads
   the next pointer as an exclusive bound. The `.You` fragment is annotated at
   `$0748D6`, followed by `.endOfTable` at `$0748D8`, but its `dw` directive
   declares six bytes; the consumer's two-byte comment-derived interval and the
   directive disagree. The consumer also references `Text_DictionaryPointers`
   while the only table declaration in the pinned file is
   `DictionaryPointers:`; no explicit alias is present. A source regression
   pins both findings, but the source/ROM interpretation remains unresolved.
3. Continue extending the project-facing authoring API: the MCP server now
   exposes read-only field-filtered searches across imported and custom
   overworld hidden-item records, preview-first packed dungeon-chest field
   edits and raw-field-filtered chest queries, plus imported
   overworld hidden-item row updates in addition to project-authored additions.
   Next, establish a verified room-payload fixture and reconcile the 320 pointer
   slots with the unresolved playable-room set before attempting room-object
   editing. Preserve source baselines, explicit constraints, alias relationships,
   deterministic exports, and the no-ROM-write boundary. The MCP-exposed
   chest/room-reference audit reports edited room values beside immutable source
   baselines but does not resolve item names or playable-room semantics.
4. Complete Phase 1 extraction and Phase 0 tool checks. The existing matching byte
   comparisons do not decode overworld map payloads, prove all source annotations,
   or establish that the whole editor pipeline works.
