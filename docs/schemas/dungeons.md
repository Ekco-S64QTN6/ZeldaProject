# Dungeon-room data schema: discovery baseline

Status: **Phase 1 research; not yet an extraction contract.** This note records
what the pinned disassembly establishes without guessing the meaning of room
object bytes. An extractor is not complete until pointer decoding is verified
against a local, clean ROM and covered by fixtures.

## Authoritative pointer table

At the pinned
[`Bank1F.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Bank1F.asm#L3-L16),
the disassembly declares `RoomData_ObjectDataPointers` at file offsets
`$0F8000–$0F83BF`. The table consists of `dl` expressions, each representing
a 24-bit (three-byte) pointer. The inclusive range is `0x3C0` bytes, or 960
bytes, which gives 320 pointer-table entries indexed `0x000–0x13F`.

For a pointer-table index `i`, the pointer-entry file offset is:

```text
pointer_entry_file_offset = 0x0F8000 + (i * 3)
```

This formula locates the pointer entry, not the room-data target. The file
offset follows the canonical headerless LoROM mapping described in
[`rom-offsets.md`](../references/rom-offsets.md).

## Count discrepancy to resolve

The roadmap currently refers to 296 dungeon rooms, while this disassembly table
spans 320 indices. Those figures must not be treated as interchangeable. The
table includes references to `RoomDataTiles_Empty` and repeated/shared target
expressions; it does not by itself establish which indices are usable playable
rooms. Preserve raw pointer-table indices in extracted data and determine the
user-facing room set only after corroborating with runtime/tool behavior.

## What the source establishes

- `RoomData_ObjectDataPointers` is located at `$0F8000–$0F83BF` in the
  pinned disassembly and contains three-byte `dl` entries.
- Entries refer to named targets including `RoomDataTiles_0000` and
  `RoomDataTiles_Empty`. The target expression, including any offset suffix,
  must be retained for auditability rather than replaced with an inferred ID.
- [`Bank0A.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Bank0A.asm#L3-L25)
  shows room-data labels mapped to `incbin "bin/rooms/roomXXXX.bin"` files,
  with sizes annotated in comments.
- At pinned disassembly commit
  `347c23f9fc019c72d32da537c9cb235f468d021d`, the tracked tree does not
  contain the referenced `bin/rooms/*.bin` payloads. The labels and some sizes
  are useful evidence, but those binary chunks are not available as ready-made
  fixtures in this repository snapshot.

## Initial extraction record

A future raw pointer-table export should preserve at least:

| Field | Meaning |
| --- | --- |
| `table_index` | Original index, integer `0–319` (hex `0x000–0x13F`) |
| `pointer_entry_file_offset` | Entry location calculated with the formula above |
| `pointer_expression` | Exact source `dl` expression, retained verbatim |
| `target_label` | Parsed label, nullable if parsing has not resolved it |
| `target_offset_expression` | Any `+$NNNN` suffix preserved separately |
| `resolved_target_file_offset` | Nullable until pointer resolution is verified against the ROM |
| `is_empty_target` | Derived only from an explicit `RoomDataTiles_Empty` reference |
| `source_revision` | Pinned disassembly revision used to interpret the table |

This is an audit-oriented discovery record, not a final SQLite schema. It keeps
the original index and source expression intact even if multiple indices point
to shared data.

## Validation gates before calling extraction complete

1. Add fixtures from a locally supplied clean US ROM or approved local test
   setup. Never commit ROMs or partial ROM slices.
2. Parse the disassembly expressions and independently decode the corresponding
   three-byte pointer entries from the local ROM, comparing each result.
3. Establish how banked/long pointers resolve to file offsets and how empty or
   shared targets should be represented. Do not infer this from labels alone.
4. Record every semantic field's source label / byte range and add deterministic
   extraction tests before exposing rooms through the authoring API.

No ROM bytes are read or written by this documentation change.
