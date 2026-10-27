# Dungeon door-data pointer table: source discovery

Status: **Phase 1 discovery; not a door-record decoder.** The pinned disassembly
has a door-data pointer table parallel to the room object-data pointer table.
This note records its layout and the source expressions that must remain intact
through extraction.

## Table location and extent

In the pinned
[`Bank1F.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Bank1F.asm),
`RoomData_DoorDataPointers` begins immediately after
`RoomData_ObjectDataPointers`:

| Table | File-offset range (inclusive) | Bytes | Entry width | Entries |
| --- | --- | ---: | ---: | ---: |
| `RoomData_ObjectDataPointers` | `$0F8000–$0F83BF` | `0x3C0` | 3 bytes (`dl`) | 320 |
| `RoomData_DoorDataPointers` | `$0F83C0–$0F877F` | `0x3C0` | 3 bytes (`dl`) | 320 |

Both table extents calculate to 960 bytes / three-byte entries = 320 entries.
The door table starts at `$0F83C0`, exactly one byte after the object table's
reported inclusive end, so the source-declared ranges are contiguous and
non-overlapping.

For an index `i` in the raw pointer table, its door-pointer entry location is:

```text
pointer_entry_file_offset = 0x0F83C0 + (i * 3)
```

Use the pointer-table index as an audit key, not as proof that a given index
is an editable/playable room. The earlier room-object note already records the
difference between the 320 pointer slots and the roadmap's 296-room claim.

## Preserve each pointer expression

Unlike the object-pointer list, the door table expressions commonly include a
label and an addend, for example:

- `RoomDataTiles_0000+$004D`
- `RoomDataTiles_0001+$0086`
- `RoomDataTiles_0002+$00F2`
- `RoomDataTiles_Empty+$0008`

Those are source expressions, not final file offsets. The labels identify the
source room-data payloads; the addends point to a position within the referenced
payload. Do not discard an addend, coerce it into a new room ID, or resolve it
as an ordinary absolute LoROM address without tracing the loader and checking
the local ROM.

The fact that the door-pointer table uses the same `RoomDataTiles_*` labels
as the object-data table suggests both tables reference different positions in
the same room-data streams. The exact byte-level boundary and door-record
encoding still needs verification; the pointer list itself does not fully
describe a room's doors.

## Empty and shared targets

The list contains explicit `RoomDataTiles_Empty+$0008` references and repeated
target expressions. Preserve each raw table slot and original expression even
when two entries share the same target. An empty room-data target must not be
silently omitted: the table index is part of the mapping, and any later
normalization should preserve the source index.

A practical first-pass record should include:

| Field | Meaning |
| --- | --- |
| `room_table_index` | Original pointer-table index, integer `0–319` |
| `pointer_entry_file_offset` | `0x0F83C0 + room_table_index * 3` |
| `pointer_expression` | Exact `dl` expression, including any addend |
| `target_label` | Parsed source label |
| `target_addend` | Parsed source addend, nullable if absent |
| `resolved_target_file_offset` | Nullable until target/pointer semantics are verified |
| `source_revision` | Pinned revision `347c23f9fc019c72d32da537c9cb235f468d021d` |

## Validation gates

1. Compare all 320 door-pointer entries with the corresponding three-byte
   values in a locally supplied clean US ROM.
2. Trace the room loader to determine how the `dl` values and symbolic
   addends resolve, and where the door-data reader starts within a room stream.
3. Validate the table index relationship between `RoomData_ObjectDataPointers`
   and `RoomData_DoorDataPointers`, including empty/shared targets.
4. Parse door records only after their byte layout, termination rule, and
   directional meaning are established from the consumer and local fixtures.
5. Keep ROMs and ROM-derived binary slices local and out of Git.

This is a source-layout note only; it does not read or write ROM bytes and does
not claim door editing is implemented.
