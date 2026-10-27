# Project data schemas

The initialized SQLite database currently has only the metadata schema
specified in [project-format.md](../project-format.md). Game-system schemas are
introduced alongside Phase 1 extractors so that every field is grounded in the
ROM layout and the pinned `AsarUSALTTPDisassembly` reference.

## Source export contracts

- [Pointer-table JSON export](./pointer-table-export.schema.json) — version 1 schema for the JSON emitted by `zelda-suite inspect-pointer-table`.
- [Incbin inventory JSON export](./incbin-inventory-export.schema.json) — version 1 schema for the JSON emitted by `zelda-suite inspect-incbin`.

## Phase 1 discovery notes

- [Dungeon rooms](./dungeons.md) — documents the discovered 320-entry room
  object-pointer table, the mismatch with the roadmap's 296-room count, and
  evidence still needed before extraction becomes a stable contract.

## Planned subsystem docs

- `overworld.md` — 160 maps, tile layers, palettes, warps.
- `dungeons.md` — rooms, headers, objects, doors, chests.
- `items.md` — item table, chest table, shop table.
- `text.md` — message table, encoding, compression.
- `sprites.md` — sprite types, placements, gfx banks.
- `audio.md` — music track pointers, sample banks.

Each schema doc must cite the corresponding label / address range in
`AsarUSALTTPDisassembly` and must not claim extraction support until its loader
and fixtures exist.
