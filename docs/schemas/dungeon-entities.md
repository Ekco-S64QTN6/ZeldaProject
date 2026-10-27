# Dungeon sprite and overlord layouts: source discovery

Status: **Phase 1 discovery, not a completed dungeon-entity extractor.**
The pinned ROM-analysis log describes the pointer list and the general record
shape, but the pointer decoding, sentinel behavior, and bitfield details must be
verified against the loader and a local clean US ROM before extraction is
treated as complete.

## Dungeon entity pointer table

The pinned
[`Logs/Zelda_3_ROM.log`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Logs/Zelda_3_ROM.log)
describes `$04D62E–$04D92E` as an array of pointers to dungeon sprite and
overlord lists. Each entry is two bytes, and lists are described as being in
room order. The same log says the table reserves space for `$180` rooms, even
though the built-in room limit is `$128`.

- `$180` entries = 384 possible pointer slots.
- `$128` entries = 296 room IDs under the current built-in limit.
- If entries are two bytes, a 384-entry pointer table occupies `0x300` bytes.

**Address-range discrepancy:** the log prints the pointer-table range as
`$04D62E–$04D92E`, whose inclusive size is `0x301` bytes, while it separately
states a size of `$300` bytes. If the stated length is correct, a zero-based
range beginning at `$04D62E` would end at `$04D92D`. Preserve both source
annotations until the actual labels/loader and local ROM resolve whether this
is an endpoint convention or a documentation off-by-one; do not silently
correct the source text.

The count also explains why the table should not be reduced to 296 entries just
because the gameplay limit is 296. The extra slots may be reserved capacity.
Preserve the raw table index and determine which entries are valid independently
of the maximum room count.

## Per-room list format (source description)

The same log says a room's list begins with one byte stored to WRAM `$0FB3`;
the log author did not know its purpose. After that byte, entity records appear
as three-byte clusters and the list ends with `$FF`.

| Byte within cluster | Source-described content | Extraction guidance |
| ---: | --- | --- |
| 0 | Y position, in units of 16 pixels from the top | Preserve raw byte; decode position and bitfields only after consumer checks |
| 1 | X position, in units of 16 pixels from the left | Preserve raw byte; source describes high bits as overlord/subtype flags |
| 2 | Sprite or overlord type | Preserve raw byte and distinguish decoded sprite vs. overlord type |

The ROM log describes the first byte as containing Y-coordinate bits, flags
that can be used to generate a subtype, and a flag for BG1 vs. BG2 priority.
For the second byte, it describes X-coordinate bits and high bits that identify
an overlord when all the relevant bits are set; partially set bits can contribute
to the subtype. The text extraction does not fully specify a trusted bit-mask
layout, so this is a record of the source description, not a byte-level decoder
specification.

This format differs from the overworld lists: the ROM log describes special
overworld logic in which values `$F3` and above in the third byte mean
overlords, while the dungeon format uses flag bits in the second byte to
distinguish sprite and overlord records. Do not share an entity decoder across
both contexts without accounting for that distinction.

## Suggested raw extraction model

Keep the pointer table and its target lists separate:

| Record | Fields to preserve |
| --- | --- |
| Dungeon pointer entry | Table index, pointer-entry file offset, raw two pointer bytes, decoded local-pointer target (nullable until verified), source revision |
| Room entity list | Room/table index, target location, leading `$0FB3`-associated byte, termination status |
| Placed entity | List-local index, record file offset, raw Y/flag byte, raw X/flag byte, raw type byte, source revision |

Do not call the first byte after the pointer target a “header” or assign semantic
meaning to `$0FB3` until the consumer confirms it. Also preserve empty lists,
sentinel placement, and any partial final record as explicit states instead of
silently dropping them.

## Validation gates

1. Trace the code that reads this pointer table to confirm the pointer base,
   bank/offset conversion, word order, and room-index selection.
2. Compare the raw two-byte pointer entries and their resolved targets against
   a locally supplied clean US ROM. Never resolve them as ordinary LoROM CPU
   addresses by assumption.
3. Locate the list parser and document the precise `$FF` sentinel test, how the
   leading byte is consumed, and the actual valid record bit masks.
4. Test the extra pointer slots (`$128–$17F`) as reserved/unknown until their
   contents and runtime use are proven; do not expose unsupported rooms in the
   authoring API.
5. Keep ROM files and ROM-derived binary slices local. Synthetic records can
   cover parser behavior before a local ROM fixture is available.

This is documentation only. It does not read or write ROM bytes and does not
claim dungeon entity extraction is implemented.
