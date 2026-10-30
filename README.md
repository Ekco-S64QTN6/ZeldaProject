# ZeldaProject

A Claude-driven, RPG Maker-style authoring suite for *The Legend of Zelda: A Link to the Past*.

- **Agent instructions:** see [`CLAUDE.md`](./CLAUDE.md)
- **Plan:** see [`ROADMAP.md`](./ROADMAP.md)
- **Tool/project catalog:** see [`RESEARCH.md`](./RESEARCH.md)
- **Contributing:** see [`CONTRIBUTING.md`](./CONTRIBUTING.md)
- **Changes and versioning:** see [`CHANGELOG.md`](./CHANGELOG.md) and [`docs/versioning.md`](./docs/versioning.md)

**Project status (2026-10-30):** Early-stage foundation and source-metadata tooling. The repository has a SQLite project store with explicit schema migration and validated source-export persistence with non-writing import previews, source-only extractors, a validated named-asset registry, read-only ROM inspection, and file-based byte-diff utilities. The source inventory now includes a 320-entry dungeon room object-pointer table and its companion 320-entry door-data pointer table, 266 source-labelled room payload declarations, an eight-entry Mad Batter pseudo-attack palette-selector table, a two-entry Crystal Switch palette-selector lookup, an eight-word Crystal Maiden palette-word export, and a nine-entry Crystal Maiden message-ID table whose eight unique IDs cross-reference existing entries in the 397-message index. Selector values are not decoded colors; both Crystal Maiden exports retain unresolved relationships between their global data labels and local routine references. The source inventory also includes a 168-entry packed `Dungeon_ChestData` inventory with raw item-byte/room-value/big-chest fields, a 243-entry inline `SpritePrep_Main` dispatch table cross-referenced by ID to all 68 `SpriteActive3_Table` entries, the two-row mixed-width Landmine OAM table with byte-accurate `dw`/`db` field offsets, the 54-word OAM allocator limit/fallback table, and source catalogs for seven standard-shopkeeper handlers, three potion transactions, three special-shop transactions (Bomb Shop bomb/Super Bomb and Bottle Vendor bottle sale), and seven paid overworld interactions (Fortune Teller, Digging Game, Zora King, Kiki, Archery Game, and Lake Hylia Fairy). These preserve source-coded fees and reward evidence; the Super Bomb's flag/tagalong reward is not a receipt-slot entry, and the Digging Game heart-piece gate remains separate from its random reward dispatch. The SpritePrep and shopkeeper inline table offsets and handler address comments remain unverified; these exports preserve source metadata rather than asserting decoded/runtime semantics. The SQLite-backed semantic editing slices are now available: the overworld hidden-item model (128 area slots, 351 source-preserving records, alias-aware relationships, constrained coordinate/value edits and consumer reclassification) and packed dungeon chest model (168 entries with separately editable raw item byte, room value and big-chest flag). Both preserve source baselines and update SQLite/JSON only. Initial imports and replacements for both semantic models now preview by default; CLI callers must pass `--apply` (Python callers must pass `dry_run=False`) to persist. Pair `--replace --apply` only after reviewing the before/proposed summary, because replacement resets imported edits. Project-authored hidden-item additions can be created, updated, and deleted with dry-run-first commands and many-to-many area aliases; the 351 imported source rows and their source alias relationships remain unchanged. General room/map-layer editing, canonical item-name resolution and ROM writing/rebuilding are **not implemented yet**. Source inventories preserve unknowns and mismatched source annotations rather than guessing at binary meanings. See the [current roadmap](./ROADMAP.md) and [extracted-data catalog](./docs/extracted-data.md). To import a committed asset by its validated registry name, run `uv run zelda-suite import-extracted-asset project/my-hack.db falling-prize-item-values`. The overworld High/Low source inventories can be checked with `uv run zelda-suite validate-overworld-payload-pairs data/extracted/overworld-payloads-bank0b.json data/extracted/overworld-payloads-bank0c.json`. For a source-line-by-source-line view of the three range/size mismatches, the missing Screen4F High range, and candidate High-to-Low adjacency, run `uv run zelda-suite audit-overworld-payload-layout data/extracted/overworld-payloads-bank0b.json data/extracted/overworld-payloads-bank0c.json`. The report does not open payload binaries or verify offsets against ROM.

The 2026-10-29 user-run read-only ROM bundle returned exit status 0 for all ten checks: 662 scalar-table values (zero mismatches, 98 unresolved), 550 overworld hidden-item comparisons (zero mismatches), all 320 dungeon-room pointers (zero mismatches, six preserved source-offset findings), all 98 dictionary pointers (zero mismatches, one separate `.You` source-extent warning), and 36,363 encoded text-message bytes (zero mismatches, seven source warnings). The ROM's size, CRC-32, SHA-1, and MD5 match the documented No-Intro USA entry, and the user confirms that it boots. The six dungeon source-comment offset findings are now bracketed by neighboring source declarations and their declared sizes; the original comments and verifier warnings remain preserved, and candidate offsets are still not ROM-verified. The `.You` extent warning, message-source warnings, 98 unresolved scalar expressions, canonical item-ID mapping, decoded map semantics, and full external-tool integration remain open. A separate user-run YAZE v0.7.2 check successfully read ROM info/raw bytes, dungeon room/sprites, graphics bytes, overworld and dungeon palette groups, and messages. However, `overworld-describe-map --screen=80` failed with `Offset 1311049 out of range (size: 1048576)`, and one dungeon-room staircase label was malformed. Static source audits traced the map error to the global `LoadDiggableTiles()` read beyond the 1 MiB image, and the malformed label to a dangling pointer from a temporary `absl::StrCat()` string. Upstream corrected these issues in [commits `566d7c6`](https://github.com/scawful/yaze/commit/566d7c6ea08b0df2addbb67940aa56794ef052fb) and [`8d4f1ad`](https://github.com/scawful/yaze/commit/8d4f1ad59f539f378ca63faa84545b59e3aa3c5b); an updated build still needs a runtime retest. `z3cli` remains untested. The YAZE smoke-test hash matched before and after; see the [ROM verification runbook](./docs/real-rom-verification.md) for exact commands and limitations.
For project-local dungeon chest authoring, run `uv run zelda-suite import-dungeon-chest-data project/my-hack.db --apply`, inspect a record with `uv run zelda-suite list-dungeon-chest-records project/my-hack.db --table-index 5`, and edit packed fields with `uv run zelda-suite update-dungeon-chest-record project/my-hack.db 0 --item-value '$AA' --room-value '$1234' --big-chest` (preview only; add `--apply` to persist). The original 24-bit source literal remains preserved; edits update SQLite/JSON only and do not write ROM bytes. Run `uv run zelda-suite audit-project-dungeon-chest-room-references project/my-hack.db` to join the **current edited** room values to the source object/door-pointer tables. Add `--fail-on-findings` for automation or `--output PATH` for a new JSON report. The report preserves original room values and edit status; its pointer offsets are source annotations, not verified ROM offsets.

For a ROM-independent view of overworld hidden-item declarations, run `uv run zelda-suite inspect-overworld-hidden-items`; comparing those source-derived offsets and bytes against a local image is a separate step documented in [`docs/real-rom-verification.md`](./docs/real-rom-verification.md).
To audit how the hidden-item third byte is interpreted by the pinned source consumer, run `uv run zelda-suite audit-overworld-hidden-item-value-semantics`. It distinguishes secret-state mask values from extended replacement-table selectors without treating them as canonical item IDs or claiming ROM verification.


The semantic models are opt-in and project-local. Initialize a project to create an isolated authoring database, then import the domain inventory you want to explore. For overworld hidden items, import the pinned disassembly, inspect one area, and edit a record:

```bash
uv run zelda-suite init my-hack
uv run zelda-suite import-overworld-hidden-items project/my-hack.db reference/AsarUSALTTPDisassembly/Bank1B.asm --apply
uv run zelda-suite list-overworld-hidden-items project/my-hack.db --area-index 0
uv run zelda-suite update-overworld-hidden-item project/my-hack.db 0 --coordinate-word '$1234' --value-byte '$84'  # preview only; add --apply to persist
# Preview only; pass --apply to commit a project-authored addition.
uv run zelda-suite create-custom-overworld-hidden-item project/my-hack.db --area-index 12 --area-index 13 --coordinate-word '$1234' --value-byte '$05'
uv run zelda-suite validate project/my-hack.db
```

Both semantic-model import commands preview the source revision, hash, record counts, and any current model by default without changing project files. Add `--apply` to persist an initial import; add `--replace --apply` only after reviewing the replacement preview because it resets imported edits (custom overworld hidden-item records and area links are preserved). Python callers use `dry_run=False` to apply.

Schema-v5 projects are created by `init`. Existing schema-v1/v2/v3/v4 projects should first run `zelda-suite migrate-project project/my-hack.db --dry-run` to simulate every upgrade step on a temporary copy, then run `zelda-suite migrate-project project/my-hack.db` to apply it. A normal invocation also safely refreshes a current project's JSON sidecar; a dry run never changes the database or sidecar. Each schema-version transition uses an explicit SQLite `BEGIN IMMEDIATE` transaction so its DDL and version metadata commit or roll back together. A multi-step upgrade may remain at its last successfully committed intermediate version if a later step fails; rerun the migration after correcting the cause. Record indexes are source-order indexes, not canonical item IDs. `update-overworld-hidden-item` and `update-dungeon-chest-record` return read-only previews by default; use CLI `--apply` or Python `dry_run=False` to persist. Both edit the project database and JSON export only; neither patches the ROM. See [`docs/project-format.md`](./docs/project-format.md).
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
ROM-specific checks are local-only and are not run by repository CI. User-run
ROM fingerprints/byte comparisons and the partial YAZE v0.7.2 smoke test are
recorded in [`docs/real-rom-verification.md`](./docs/real-rom-verification.md);
open integration gates remain in [`ROADMAP.md`](./ROADMAP.md). Setup and CI
remain ROM-independent.
For a staged, read-only local-ROM smoke test and selected table-byte checks,
follow [`docs/real-rom-verification.md`](./docs/real-rom-verification.md). To
run the bundled read-only checks in one pass, set `ROM` in that shell and run
`bash scripts/verify-rom-readonly.sh "$ROM"`. It creates a fresh report
directory, preserves each JSON report plus a `checks.tsv` status summary, and
returns nonzero if a check fails; it never modifies the ROM. A size check is
not proof of canonical ROM provenance.

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

For a read-only check of the 98 text-dictionary pointer words, run `uv run zelda-suite verify-text-dictionary-pointers PATH_TO_ROM`. Ordinary entries use source-commented fragment starts; the final pointer uses the exclusive end after the inclusive data-range annotation. Report v2 preserves that raw end comment and the separate `.You` extent warning. The pinned consumer reads `Text_DictionaryPointers+0/+2`, while the only visible declaration is `DictionaryPointers:` and no explicit alias appears in the file. The `.You` directive declares six bytes inside a two-byte comment-derived interval, while the runtime uses the next pointer as an exclusive bound. A source regression pins both findings; neither is repaired or claimed as ROM-verified. The command does not verify ROM provenance or fragment payload bytes or decode text; see [the text documentation](./docs/schemas/text.md) and [the real-ROM runbook](./docs/real-rom-verification.md).

For a read-only byte comparison of the 397 pinned text messages against a local image, use `uv run zelda-suite verify-text-message-bytes PATH_TO_ROM` with two `--block` options. It compares literal source bytes but does not decode messages or independently verify the source offsets; see [the text schema guide](./docs/schemas/text.md).


## Optional project MCP server

The optional stdio server exposes a small, project-bound subset of the validated
authoring API to an MCP-compatible host. It binds one existing SQLite database
and the registered source-asset manifest at startup; tool arguments cannot
select a different database, manifest, or filesystem path. Install the optional
SDK dependency and run:

```bash
uv sync --extra agent
uv run zelda-suite-mcp \
  --database project/my-hack.db \
  --registry data/extracted/manifest.json
```

Alternatively, set `ZELDA_SUITE_PROJECT_DB` and omit `--database`. The tool
surface includes project validation/source-asset reads, overworld hidden-item
reads and preview-first imported hidden-item record updates, dungeon chest
reads with optional single-entry chest selection, bounded packed-chest field
edits, a read-only chest-to-room-pointer audit, plus project-authored
hidden-item create/update/delete. Set `--registry` (or `ZELDA_SUITE_ASSET_REGISTRY`) to the
registered asset manifest. All mutation tools default to previews; `apply=true`
explicitly persists the project-local SQLite/JSON change while preserving
source baselines and area aliases. Source imports, ROM access, and ROM writes
are not exposed. See
[`docs/mcp-server.md`](./docs/mcp-server.md) for the tool contract and limits.
