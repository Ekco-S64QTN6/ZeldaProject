# Project data schemas

The initialized SQLite database currently has only the metadata schema
specified in [project-format.md](../project-format.md). Game-system schemas are
introduced alongside Phase 1 extractors so that every field is grounded in the
ROM layout and the pinned `AsarUSALTTPDisassembly` reference.

## Source export contracts

The supported version-1 source exports can be loaded and validated with the [asset loader](../asset-loader.md).

- [Pointer-table JSON export](./pointer-table-export.schema.json) — version 1 schema for the JSON emitted by `zelda-suite inspect-pointer-table`.
- [Incbin inventory JSON export](./incbin-inventory-export.schema.json) — version 1 schema for the JSON emitted by `zelda-suite inspect-incbin`.
- [ROM file-diff JSON export](./rom-file-diff-export.schema.json) — version 1 schema for the audit JSON emitted by `zelda-suite diff-rom`.
- [Raw data-table JSON export](./data-table-export.schema.json) — version 1 schema for the `db`/`dw`/`dl` expressions emitted by `zelda-suite inspect-data-table`.

## Committed source-derived data

- [`data/extracted/falling-prize-item-values.json`](../../data/extracted/falling-prize-item-values.json) — validated seven-entry item-value table with pinned source provenance; see [reproduction instructions](../extracted-data.md).

## Phase 1 discovery notes

- [Dungeon rooms](./dungeons.md) — documents the discovered 320-entry room
  object-pointer table, the mismatch with the roadmap's 296-room count, and
  evidence still needed before extraction becomes a stable contract.
- [Overworld payloads](./overworld.md) — high/low per-screen `incbin` layout,
  source-declared offsets/sizes, and limits of the current evidence.
- [Overworld hidden items](./overworld-hidden-items.md) — 128-entry pointer
  table and three-byte record description, including an unresolved size-tail
  discrepancy that must be reconciled before parsing.
- [Falling-prize item lookup](./falling-prize-items.md) — seven-entry
  `AddPendantOrCrystal` item-value table and the adjacent indexed arrays.

## Planned subsystem docs

- `overworld.md` — full editable map schema (tiles, layers, palettes, warps); the current file is discovery-only.
- `dungeons.md` — rooms, headers, objects, doors, chests.
- `items.md` — item table, chest table, shop table.
- `text.md` — message table, encoding, compression.
- `sprites.md` — sprite types, placements, gfx banks.
- `audio.md` — music track pointers, sample banks.

Each schema doc must cite the corresponding label / address range in
`AsarUSALTTPDisassembly` and must not claim extraction support until its loader
and fixtures exist.
