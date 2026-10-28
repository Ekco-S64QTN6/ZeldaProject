# Items and chest-data discovery

This page documents one source inventory, not a complete editable item/chest/shop
schema. The registered [`dungeon-chest-data`](../../data/extracted/dungeon-chest-data.json)
asset preserves the 168 packed three-byte `dl` records under
`Dungeon_ChestData` in the pinned `Bank01.asm` revision.

## Packed record fields

The pinned source comments define the 24-bit record shape:

- The top byte is the raw item value to give.
- The low 15 bits are the room value.
- Bit 15 (`0x8000`) marks a big-chest entry.

The source consumer walks entries in three-byte steps, finds the current room's
matching record, uses the top byte as the item value, and tests bit 15 to take
the big-chest path. The inventory keeps raw values and original expressions; it
does not map item bytes to names, infer shop inventory, or assert the commented
range `$00E96E-$00EB65` as a verified ROM/file offset.

## Source-only audit

Run:

```bash
uv run zelda-suite audit-dungeon-chest-data
uv run zelda-suite audit-dungeon-chest-data --output /tmp/dungeon-chest-audit.json
```

The audit reports 168 records, 106 unique room values, 32 repeated room-value
groups, 11 big-chest flags, 157 entries without that flag, and 33 distinct raw
item values. Repeated room values are retained because the source consumer
iterates among multiple chest records for the same room.

The versioned schemas are
[`dungeon-chest-data-export.schema.json`](./dungeon-chest-data-export.schema.json)
and [`dungeon-chest-data-audit.schema.json`](./dungeon-chest-data-audit.schema.json).

Remaining work includes resolving raw item values to a semantic item catalog,
connecting chest records to editable room/chest placements, validating source
offsets against a trusted ROM, and reconciling the source format with a verified
writer or YAZE/z3ed round-trip.
