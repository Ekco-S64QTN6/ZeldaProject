# Authoring API

Status: **not yet designed**. Target: Phase 2 (see `ROADMAP.md`).

This document will define the semantic surface Claude uses to make edits —
`list_rooms`, `get_room(room_id)`, `update_chest(chest_id, item_id)`,
`move_entrance(entrance_id, room_id)`, `set_tile(map_id, x, y, tile_id)`, etc.

Design constraints (from CLAUDE.md §7):

1. Every mutating call supports `dry_run=True`.
2. Every response cites the extracted data file and the disassembly label(s).
3. Referential integrity is enforced at this layer, not the byte layer.
