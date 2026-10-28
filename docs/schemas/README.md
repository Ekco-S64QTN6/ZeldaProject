# Project data schemas

The project database uses schema v2 for project metadata and validated source-export snapshots; see [project-format.md](../project-format.md). Editable game-system schemas are introduced alongside Phase 1 extractors so that every field is grounded in the ROM layout and the pinned `AsarUSALTTPDisassembly` reference.

[Version and compatibility rules](../versioning.md) explain how the registry, project format, SQLite schema, and source-export formats evolve.

## Source export contracts

The versioned source exports can be loaded and validated with the [asset loader](../asset-loader.md); data-table exports support versions 1 and 2.

- [Pointer-table JSON export](./pointer-table-export.schema.json) — version 1 schema for the JSON emitted by `zelda-suite inspect-pointer-table`.
- [Incbin inventory JSON export](./incbin-inventory-export.schema.json) — version 1 schema for the JSON emitted by `zelda-suite inspect-incbin`.
- [Incbin inventory audit report](./incbin-inventory-audit.schema.json) — version 1 source-only cross-inventory report emitted by `zelda-suite audit-incbin-inventory`.
- [Source-table expression audit report](./source-expression-audit.schema.json) — version 1 ROM-independent inventory of unresolved expressions emitted by `zelda-suite audit-unresolved-table-expressions`.
- [ROM file-diff JSON export](./rom-file-diff-export.schema.json) — version 1 schema for the audit JSON emitted by `zelda-suite diff-rom`.
- [ROM scalar-table verification report](./rom-table-verification.schema.json) — version 1 read-only report emitted by `zelda-suite verify-rom-tables` by default.
- [ROM scalar-table verification report (v2)](./rom-table-verification-v2.schema.json) — opt-in report emitted by `zelda-suite verify-rom-tables --include-skipped-expressions`; includes non-evaluating syntax classifications for skipped expressions.
- [Overworld hidden-item verification report](./overworld-hidden-item-verification.schema.json) — version 1 report emitted by `zelda-suite verify-overworld-hidden-items`; includes source-derived sentinel-delimited per-area lists.
- [Overworld hidden-item source-layout report](./overworld-hidden-item-source-layout.schema.json) — version 1 source-only report emitted by `zelda-suite inspect-overworld-hidden-items`; it does not read a ROM or decode semantic values.
- [Dungeon-room pointer verification report](./dungeon-room-pointer-verification.schema.json) — version 1 read-only report emitted by `zelda-suite verify-dungeon-room-pointers`; checks long pointer bytes against source-commented candidate targets.
- [Dungeon-room asset cross-reference audit](./dungeon-room-asset-audit.schema.json) — version 1 source-only join between the 320-slot pointer export and the three registered payload inventories.
- [Joined receive-item layout](./item-receipt-layout.schema.json) — version 1 positional join of six raw receive-item tables, with the 14 dungeon masks retained separately and canonical item IDs explicitly unresolved.
- [Mixed-width data-table export](./mixed-data-table-export.schema.json) — version 1 schema for colon-separated `db`/`dw`/`dl` source fields, emitted by `zelda-suite inspect-mixed-data-table`.
- [OAM allocation audit](./oam-allocation-audit.schema.json) — version 1 source-only report grouping six OAM limits and 48 fallback points into six regions.
- [Raw data-table JSON export](./data-table-export.schema.json) — version 1 schema for the `db`/`dw`/`dl` expressions emitted by `zelda-suite inspect-data-table`.
- [Raw data-table JSON export with comments](./data-table-export-v2.schema.json) — version 2 schema for `zelda-suite inspect-data-table --include-comments`; adds the original inline comment to each entry.
- [Dictionary fragment inventory](./dictionary-inventory-export.schema.json) — version 1 metadata schema for `zelda-suite inspect-text-dictionary`.
- [Text dictionary cross-reference audit](./text-dictionary-audit.schema.json) — version 1 source-only report emitted by `zelda-suite audit-text-dictionary`; pointer values remain unresolved and offsets remain unverified.
- [Text dictionary pointer verification report](./text-dictionary-pointer-verification.schema.json) — version 1 read-only byte comparison against candidate 16-bit pointers derived from the registered fragment offsets; source offsets, ROM provenance, and the runtime symbol-name mapping remain unverified.
- [Text message index](./text-message-index.schema.json) — version 1 metadata schema for `zelda-suite inspect-text-messages`.
- [Text-message index audit](./text-message-index-audit.schema.json) — version 1 source-only diagnostics emitted by `zelda-suite audit-text-message-index`.
- [Text-message byte verification](./text-message-byte-verification.schema.json) — version 1 read-only comparison of source-literal message bytes against a local ROM; does not decode text or establish ROM provenance/source-offset trust.
- [Named asset registry](./asset-registry.schema.json) — version 1 catalog schema for `data/extracted/manifest.json`.
- [Sprite dispatch export](./sprite-dispatch-export.schema.json) — version 1 schema for `zelda-suite inspect-sprite-dispatch`.
- [SpritePrep dispatch export](./sprite-prep-dispatch-export.schema.json) — version 1 schema for the inline, source-commented 243-entry `SpritePrep_Main` table, whose exact table offset remains unset.
- [SpritePrep/SpriteActive3 cross-reference audit](./sprite-prep-dispatch-audit.schema.json) — version 1 source-only join by sprite ID, not a handler-semantics equivalence claim.
- [Music track index](./music-track-index.schema.json) — version 1 schema for `zelda-suite inspect-music-track-index`.
- [Music asset cross-reference audit](./music-asset-audit.schema.json) — version 1 source-only join between registered music pointer targets and payload declarations.
- [Overworld High/Low pair check](./overworld.md) — validates that each source-local screen token has one High and one Low payload declaration.

## Committed source-derived data

- [`manifest.json`](../../data/extracted/manifest.json) — registry of the thirty-five named source exports and their expected formats, counts, and pinned revision.
- [`data/extracted/crystal-maiden-message-ids.json`](../../data/extracted/crystal-maiden-message-ids.json) — nine source-declared `dw` message IDs cross-referenced to the text-message index; linkage to the routine's local `.message_ids` remains unresolved.
- [`data/extracted/crystal-maiden-palette-words.json`](../../data/extracted/crystal-maiden-palette-words.json) — eight raw 16-bit words, with linkage to the routine's local `.palette` reference unresolved.
- [`data/extracted/crystal-switch-palette-selectors.json`](../../data/extracted/crystal-switch-palette-selectors.json) — two source-derived selector bytes, not decoded color values or ROM-verified bytes.
- [`data/extracted/mad-batter-pseudo-attack-palettes.json`](../../data/extracted/mad-batter-pseudo-attack-palettes.json) — eight source-derived selector bytes, not decoded color values or ROM-verified bytes.

- [`data/extracted/falling-prize-item-values.json`](../../data/extracted/falling-prize-item-values.json) — item values.
- [`data/extracted/falling-prize-fall-heights.json`](../../data/extracted/falling-prize-fall-heights.json) — indexed falling heights.
- [`data/extracted/falling-prize-y-offsets.json`](../../data/extracted/falling-prize-y-offsets.json) — indexed Y offsets.
- [`data/extracted/falling-prize-x-offsets.json`](../../data/extracted/falling-prize-x-offsets.json) — indexed X offsets.
- [`data/extracted/falling-prize-delay-timers.json`](../../data/extracted/falling-prize-delay-timers.json) — indexed delay timers.
- [`data/extracted/text-dictionary-pointers.json`](../../data/extracted/text-dictionary-pointers.json) — 98 symbolic dictionary-fragment pointer expressions.
- [`data/extracted/text-dictionary-fragments.json`](../../data/extracted/text-dictionary-fragments.json) — pointer-to-fragment metadata, including the unresolved `.You` source-size mismatch.
- [`data/extracted/text-message-index.json`](../../data/extracted/text-message-index.json) — 397 message IDs with source-derived offsets and size diagnostics.
- [`data/extracted/sprite-active3-dispatch.json`](../../data/extracted/sprite-active3-dispatch.json) — 68 source-mapped handler entries for sprite IDs `$79–$BC`.
- [`data/extracted/sprite-prep-dispatch.json`](../../data/extracted/sprite-prep-dispatch.json) — 243 source-commented prep-dispatch entries for IDs `$00–$F2`; the inline-table file offset remains unestablished.
- [`data/extracted/music-track-index.json`](../../data/extracted/music-track-index.json) — 35 source-indexed music pointer expressions, with empty entries and aliases.
- [`data/extracted/music-payload-inventory.json`](../../data/extracted/music-payload-inventory.json) — 15 song payload `incbin` declarations with source ranges and size diagnostics.
- [`data/extracted/overworld-hidden-item-pointers.json`](../../data/extracted/overworld-hidden-item-pointers.json) — 128 area-to-hidden-item-list pointers; record boundaries remain unresolved.
- [`data/extracted/dungeon-room-object-pointers.json`](../../data/extracted/dungeon-room-object-pointers.json) — 320 source-indexed 24-bit dungeon room pointer expressions; a read-only verifier compares candidate addresses from the registered payload inventories, but local-ROM verification remains open.
- [`data/extracted/dungeon-room-door-pointers.json`](../../data/extracted/dungeon-room-door-pointers.json) — 320 source-indexed `RoomData_DoorDataPointers` expressions with numeric addends; target labels match object-pointer slots, but addend meaning and local-ROM verification remain open.
- [`data/extracted/landmine-oam-groups.json`](../../data/extracted/landmine-oam-groups.json) — two mixed-width Landmine OAM rows; raw field widths and offsets only, not decoded OAM semantics.
- [`data/extracted/oam-buffer-position-table.json`](../../data/extracted/oam-buffer-position-table.json) — 54 OAM allocator words: six limits and 48 fallback entries grouped into six source-derived regions; not runtime- or ROM-verified.
- [`data/extracted/dungeon-room-payloads-bank03.json`](../../data/extracted/dungeon-room-payloads-bank03.json) — 34 Bank03 room `incbin` declarations with source start offsets and size annotations.
- [`data/extracted/dungeon-room-payload-inventory.json`](../../data/extracted/dungeon-room-payload-inventory.json) — 75 Bank0A room `incbin` declarations with start-offset and size annotations.
- [`data/extracted/dungeon-room-payloads-bank1f.json`](../../data/extracted/dungeon-room-payloads-bank1f.json) — 157 Bank1F room `incbin` declarations with source start offsets and size annotations.
- [`data/extracted/overworld-payloads-bank0b.json`](../../data/extracted/overworld-payloads-bank0b.json) — 164 Bank0B high/low `incbin` declarations with offset/size diagnostics.
- [`data/extracted/overworld-payloads-bank0c.json`](../../data/extracted/overworld-payloads-bank0c.json) — 84 Bank0C high/low `incbin` declarations with offset/size diagnostics.
- [`data/extracted/item-receipt-target-addresses.json`](../../data/extracted/item-receipt-target-addresses.json) — 76 raw two-byte WRAM target addresses.
- [`data/extracted/item-receipt-values.json`](../../data/extracted/item-receipt-values.json) — 76 raw byte values used by the receive-item routine.
- [`data/extracted/item-receipt-dungeon-masks.json`](../../data/extracted/item-receipt-dungeon-masks.json) — 14 two-byte dungeon-item masks.
- [`data/extracted/item-receipt-y-offsets.json`](../../data/extracted/item-receipt-y-offsets.json) — 76 raw Y-offset expressions.
- [`data/extracted/item-receipt-x-offsets.json`](../../data/extracted/item-receipt-x-offsets.json) — 76 X offsets.
- [`data/extracted/item-receipt-wide-flags.json`](../../data/extracted/item-receipt-wide-flags.json) — 76 raw wide-item flags.
- [`data/extracted/item-receipt-properties.json`](../../data/extracted/item-receipt-properties.json) — 76 raw property bytes.
- [`data/extracted/item-receipt-layout.json`](../../data/extracted/item-receipt-layout.json) — joined 76-position receive-item view with raw source traceability and a separate 14-mask table; it does not resolve canonical item IDs.
- [`data/extracted/item-receipt-graphics-indices.json`](../../data/extracted/item-receipt-graphics-indices.json) — 76 raw graphics-index bytes with source comments preserved; comment IDs skip `0x40` and are not canonicalized.

All exports retain pinned source provenance; see [reproduction instructions](../extracted-data.md).

## Phase 1 discovery notes

- [Dungeon rooms](./dungeons.md) — documents the discovered 320-entry room
  object-pointer table, the mismatch with the roadmap's 296-room count, and
  evidence still needed before extraction becomes a stable contract.
- [Overworld payloads](./overworld.md) — high/low per-screen `incbin` layout,
  source-declared offsets/sizes, and limits of the current evidence.
- [Overworld hidden items](./overworld-hidden-items.md) — 128-entry pointer
  table, source-level three-byte reader/sentinel behavior, declared-width
  accounting, and the new read-only ROM comparison tool. Running the tool
  against a trusted local ROM and verifying value semantics remain open.
- [Falling-prize item lookup](./falling-prize-items.md) — seven-entry
  `AddPendantOrCrystal` item-value table and the adjacent indexed arrays.
- [Audio](./audio.md) — source music pointer index, payload declarations, and the unmatched `Song0B_FairyTheme` target; payload binaries are not tracked.

## Planned subsystem docs

- `overworld.md` — full editable map schema (tiles, layers, palettes, warps); the current file is discovery-only.
- `dungeons.md` — rooms, headers, objects, doors, chests.
- `items.md` — item table, chest table, shop table.
- `text.md` — message table, encoding, compression.
- `sprites.md` — sprite types, placements, gfx banks.
- `audio.md` — source discovery for music pointer and payload inventories; semantic audio schema and payload decoding remain future work.

Each schema doc must cite the corresponding label / address range in
`AsarUSALTTPDisassembly` and must not claim extraction support until its loader
and fixtures exist.

The committed sprite dispatch export can be checked without the disassembly submodule; its regression test pins the `$79–$BC` range, source offsets, revision, and six handler alias groups. Handler address comments remain source annotations and are not independently verified ROM pointers.
