# Project data schemas

The initialized SQLite database currently has only the metadata schema
specified in [project-format.md](../project-format.md). Game-system schemas are
introduced with the Phase 1 extractors so that every field can be grounded in
the ROM layout and the pinned `AsarUSALTTPDisassembly` reference.

Planned subsystem docs:

- `overworld.md` — 160 maps, tile layers, palettes, warps.
- `dungeons.md` — rooms, headers, objects, doors, chests.
- `items.md` — item table, chest table, shop table.
- `text.md` — message table, encoding, compression.
- `sprites.md` — sprite types, placements, gfx banks.
- `audio.md` — music track pointers, sample banks.

Each schema doc must cite the corresponding label / address range in
`AsarUSALTTPDisassembly` and must not claim extraction support until its loader
and fixtures exist.
