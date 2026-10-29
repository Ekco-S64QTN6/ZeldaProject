# ZeldaProject

A Claude-driven, RPG Maker-style authoring suite for *The Legend of Zelda: A Link to the Past*.

- **Agent instructions:** see [`CLAUDE.md`](./CLAUDE.md)
- **Plan:** see [`ROADMAP.md`](./ROADMAP.md)
- **Tool/project catalog:** see [`RESEARCH.md`](./RESEARCH.md)
- **Contributing:** see [`CONTRIBUTING.md`](./CONTRIBUTING.md)
- **Changes and versioning:** see [`CHANGELOG.md`](./CHANGELOG.md) and [`docs/versioning.md`](./docs/versioning.md)

**Project status (2026-10-28):** Early-stage foundation and source-metadata tooling. The repository has a SQLite project store with explicit schema migration and validated source-export persistence, source-only extractors, a validated named-asset registry, read-only ROM inspection, and file-based byte-diff utilities. The source inventory now includes a 320-entry dungeon room object-pointer table and its companion 320-entry door-data pointer table, 266 source-labelled room payload declarations, an eight-entry Mad Batter pseudo-attack palette-selector table, a two-entry Crystal Switch palette-selector lookup, an eight-word Crystal Maiden palette-word export, and a nine-entry Crystal Maiden message-ID table whose eight unique IDs cross-reference existing entries in the 397-message index. Selector values are not decoded colors; both Crystal Maiden exports retain unresolved relationships between their global data labels and local routine references. The source inventory also includes a 168-entry packed `Dungeon_ChestData` inventory with raw item-byte/room-value/big-chest fields, a 243-entry inline `SpritePrep_Main` dispatch table cross-referenced by ID to all 68 `SpriteActive3_Table` entries, the two-row mixed-width Landmine OAM table with byte-accurate `dw`/`db` field offsets, the 54-word OAM allocator limit/fallback table, and source catalogs for seven standard-shopkeeper handlers, three potion transactions, three special-shop transactions (Bomb Shop bomb/Super Bomb and Bottle Vendor bottle sale), and seven paid overworld interactions (Fortune Teller, Digging Game, Zora King, Kiki, Archery Game, and Lake Hylia Fairy). These preserve source-coded fees and reward evidence; the Super Bomb's flag/tagalong reward is not a receipt-slot entry, and the Digging Game heart-piece gate remains separate from its random reward dispatch. The SpritePrep and shopkeeper inline table offsets and handler address comments remain unverified; these exports preserve source metadata rather than asserting decoded/runtime semantics. Semantic game editing and ROM writing/rebuilding are **not implemented yet**. Source inventories preserve unknowns and mismatched source annotations rather than guessing at binary meanings. See the [current roadmap](./ROADMAP.md) and [extracted-data catalog](./docs/extracted-data.md). To import a committed asset by its validated registry name, run `uv run zelda-suite import-extracted-asset project/my-hack.db falling-prize-item-values`. The overworld High/Low source inventories can be checked with `uv run zelda-suite validate-overworld-payload-pairs data/extracted/overworld-payloads-bank0b.json data/extracted/overworld-payloads-bank0c.json`. For a source-line-by-source-line view of the three range/size mismatches, the missing Screen4F High range, and candidate High-to-Low adjacency, run `uv run zelda-suite audit-overworld-payload-layout data/extracted/overworld-payloads-bank0b.json data/extracted/overworld-payloads-bank0c.json`. The report does not open payload binaries or verify offsets against ROM.
For a ROM-independent view of overworld hidden-item declarations, run `uv run zelda-suite inspect-overworld-hidden-items`; comparing those source-derived offsets and bytes against a local image is a separate step documented in [`docs/real-rom-verification.md`](./docs/real-rom-verification.md).
To audit how the hidden-item third byte is interpreted by the pinned source consumer, run `uv run zelda-suite audit-overworld-hidden-item-value-semantics`. It distinguishes secret-state mask values from extended replacement-table selectors without treating them as canonical item IDs or claiming ROM verification.

## Quickstart

Prepare dependencies and initialize a project without a game ROM:

```bash
bash scripts/setup.sh --name my-hack
# Windows PowerShell: .\scripts\setup.ps1 -Name my-hack
```

The setup script prefers `uv` and falls back to a Python 3.12+ virtual
environment when needed. It refuses to overwrite an existing project, then
validates the created SQLite database and JSON sidecar. It does not download,
copy, open, or modify a ROM.

For local ROM/tool diagnostics later, place an authorized clean US dump at
`base_game_roms/Legend of Zelda, The - A Link to the Past (U) [!].smc` and run
`just doctor`. That command fails when the ROM is missing or incorrectly sized;
its size check is not proof of ROM provenance or correctness, and tool checks
only confirm executables are on `PATH`. Run `zelda-suite inspect-rom PATH`
for read-only size, SHA-256, header assessment, and LoROM mapping diagnostics.
These checks have not been established by repository CI; see the open Phase 0
gates in [`ROADMAP.md`](./ROADMAP.md). Setup and CI remain ROM-independent.
For a staged, read-only local-ROM smoke test and selected table-byte checks,
follow [`docs/real-rom-verification.md`](./docs/real-rom-verification.md).

For setup and diagnostics, see [`docs/install.md`](./docs/install.md) and [`docs/doctor.md`](./docs/doctor.md). For read-only local-ROM checks, including `zelda-suite verify-rom-tables`, `zelda-suite verify-overworld-hidden-items`, and `zelda-suite verify-dungeon-room-pointers`, see [`docs/real-rom-verification.md`](./docs/real-rom-verification.md). Also see [`docs/project-format.md`](./docs/project-format.md) for the SQLite/JSON project format, [`docs/disassembly-parser.md`](./docs/disassembly-parser.md) for pointer-table inspection, [`docs/data-table-parser.md`](./docs/data-table-parser.md) for raw `db`/`dw`/`dl` tables, [`docs/asset-loader.md`](./docs/asset-loader.md) for validating source-export JSON, [`docs/project-assets.md`](./docs/project-assets.md) for importing validated source exports into a project, [`docs/rom-image-inspection.md`](./docs/rom-image-inspection.md) for local ROM metadata and LoROM offset mapping, [`docs/rom-diff.md`](./docs/rom-diff.md) for file-backed ROM diff usage, and [`docs/extracted-data.md`](./docs/extracted-data.md) for committed source-derived table exports.

For a source-only audit of registered `incbin` inventories—covering missing offset/size metadata, explicit range mismatches, and candidate overlaps—run `uv run zelda-suite audit-incbin-inventory`. Its findings do not establish ROM offsets or read payload/ROM bytes; see [`docs/incbin-inventory.md`](./docs/incbin-inventory.md).

For a ROM-independent inventory of unresolved scalar-table expressions, run `uv run zelda-suite audit-unresolved-table-expressions`. It lists raw source expressions and conservative syntax-shape classifications without evaluating them; see [`docs/data-table-parser.md`](./docs/data-table-parser.md).

For a source-only cross-check of the 98 symbolic text-dictionary pointers and fragment records, run `uv run zelda-suite audit-text-dictionary`. It preserves the known `.You` source-extent mismatch and does not read a ROM; see [`docs/schemas/text.md`](./docs/schemas/text.md).

For a source-only summary of the 397-message index's known offset-annotation and block-size discrepancies, run `uv run zelda-suite audit-text-message-index`. It does not read a ROM or decode messages; see [`docs/schemas/text.md`](./docs/schemas/text.md).

For a source-only join of the 35-slot music pointer table and its 15 payload declarations, run `uv run zelda-suite audit-music-assets`. It reports the unmatched `Song0B_FairyTheme` target and three missing size annotations without reading audio bytes; see [`docs/schemas/audio.md`](./docs/schemas/audio.md).

For a structured, source-only view of the OAM allocator, run `uv run zelda-suite audit-oam-allocation`. It groups six upper-limit words with 48 fallback points across regions A–F and does not verify ROM offsets or runtime OAM positions; see [`docs/schemas/sprites.md`](./docs/schemas/sprites.md).

For a source-only view of packed dungeon chest records, run `uv run zelda-suite audit-dungeon-chest-data`. It summarizes raw room/item values, repeated room values, and the source-commented big-chest flag without resolving item names or verifying range offsets; see [`docs/schemas/items.md`](./docs/schemas/items.md).

To cross-reference the 168 packed chest records with their object/door pointer slots using the pinned `Bank01.asm` consumer, run `uv run zelda-suite audit-dungeon-chest-room-references`. This checks source-table index consistency only; it does not verify ROM offsets or resolve the playable-room set.

For a source-only catalog of the seven standard shopkeeper purchase handlers, run `uv run zelda-suite audit-shop-item-handlers`. It cross-references source-coded price bytes with raw receive-item slots by positional index; it does not resolve item names or infer shop stock by room.

For the three potion-shop transactions, run `uv run zelda-suite audit-potion-shop-transactions`. It records source checks/deductions of 60, 160, and 120 rupees, receipt selectors `$2F/$30/$2E`, and joins those indexes to raw receipt fields and comment annotations. Runtime price behavior, canonical item IDs, and room-specific stock remain unresolved.

For the Bomb Shop and Bottle Vendor purchase paths, run `uv run zelda-suite audit-special-shop-transactions`. It records the 100-rupee bomb and bottle purchases, plus the Super Bomb's flag/tagalong reward without inventing a receipt selector. The two receipt selectors join to raw receipt slots; source ranges, runtime price behavior, and semantic item IDs remain unverified.

For source-derived non-shop fees and minigame costs, run `uv run zelda-suite audit-paid-overworld-interactions`. It covers seven interactions, including 10/15/20/30-rupee fortune readings, the 80-rupee Digging Game, 500-rupee Flippers, Kiki's 10/100-rupee fees, 20-rupee archery, and 5/20/25/50-rupee Fairy Pond donations. The Digging Game reward paths are preserved separately; source annotations and runtime behavior are not treated as ROM-verified facts.

To expose a source-comment discrepancy in the receive-item graphics table, run `uv run zelda-suite audit-item-receipt-annotations`. The 76 dense slots use indexes `$00–$4B`, while the comments omit `$40` and label the final 12 slots `$41–$4C`; the audit preserves that as a discrepancy rather than normalizing it into canonical item IDs.

The committed `SpritePrep_Main` export preserves 243 source-commented preparation entries (IDs `$00–$F2`) without inventing an inline-table offset; `uv run zelda-suite audit-sprite-prep-dispatch` joins its ID range with the 68 `SpriteActive3_Table` entries and reports the 68 shared IDs. This is index-domain cross-reference only, not proof that the handlers or annotated addresses have equivalent runtime semantics. The existing sprite dispatch export also has a submodule-independent baseline for its 68 IDs (`$79–$BC`), offsets, and six handler alias groups; handler-address comments remain unverified annotations.

The 128-entry overworld hidden-item pointer export also has a source-independent CI baseline for all target labels and pointer offsets; that baseline checks metadata consistency, not ROM bytes or resolved target offsets.

For a source-only cross-check of the 320 dungeon room pointers against the three committed room-payload inventories, run `uv run zelda-suite audit-dungeon-room-assets`. It reports the three unreferenced payload labels without reading ROM bytes or resolving candidate offsets; see [`docs/schemas/dungeons.md`](./docs/schemas/dungeons.md).

For a source-only cross-check of all 320 dungeon door-pointer addends against target payload sizes and matching object-pointer slots, run `uv run zelda-suite audit-dungeon-room-door-pointers`. The addends fit the current source-declared sizes, but this does not verify offsets or door semantics against a ROM; see the [dungeon documentation](./docs/schemas/dungeons.md).

For a read-only check of the 98 text-dictionary pointer words against candidate values derived from the registered fragment offsets, run `uv run zelda-suite verify-text-dictionary-pointers PATH_TO_ROM`. The command compares bytes only and does not verify ROM provenance, source-offset accuracy, fragment payload bytes, or the unresolved `Text_DictionaryPointers`/ `DictionaryPointers` symbol-name mapping; see [the text documentation](./docs/schemas/text.md).

For a read-only byte comparison of the 397 pinned text messages against a local image, use `uv run zelda-suite verify-text-message-bytes PATH_TO_ROM` with two `--block` options. It compares literal source bytes but does not decode messages or independently verify the source offsets; see [the text schema guide](./docs/schemas/text.md).
