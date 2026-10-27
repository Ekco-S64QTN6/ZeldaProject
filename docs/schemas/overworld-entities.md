# Overworld sprite and overlord layouts: source discovery

Status: **Phase 1 discovery, not a complete sprite schema or extractor.**
The pinned disassembly's ROM-analysis log describes the byte layouts and the
main table ranges, but the pointer targets and all entry counts must still be
checked against a local clean US ROM and the loading code.

## Three distinct data layers

Do not merge the following into one “sprite table”:

1. **Per-area pointer arrays** select a list for the current story state.
2. **Placed-entity records** describe entities in a list as coordinate/type
   triples terminated by a sentinel.
3. **Sprite statistics arrays** hold per-sprite-type metadata such as HP and
   damage. These are indexed by sprite type, not by overworld area.

The source references for this note are the pinned
[`Logs/Zelda_3_ROM.log`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Logs/Zelda_3_ROM.log)
and
[`Logs/Zelda_3_RAM.log`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Logs/Zelda_3_RAM.log),
at disassembly revision `347c23f9fc019c72d32da537c9cb235f468d021d`.

## Story-state pointer arrays

The ROM log ties the active table to the story-progress value at SRAM address
`$7EF3C5`:

| Story state | Value(s) | Source-commented pointer-array range | Inclusive byte length |
| --- | --- | --- | ---: |
| Beginning | `$00`, `$01` | `$04C881–$04C900` | `0x80` (128) |
| First Part | `$02` | `$04C901–$04CA20` | `0x120` (288) |
| Second Part | `$03` | `$04CA21–$04CB40` | `0x120` (288) |

The log explicitly says the Beginning array has data for areas `$00–$3F` only.
That is 64 areas, consistent with a two-byte pointer per area across a 128-byte
range. The later ranges are each 288 bytes; **if** these are also two-byte local
pointers, each contains 144 entries. Treat that width/count as an arithmetic
inference pending confirmation from the pointer-loading routine, not a settled
schema fact.

The log also describes a practical quirk: during Beginning mode, only the
first 64 areas have intended data, so entering a Dark World area can cause the
game to use unintended light-world sprite data. Preserve the story-state table
and source indices rather than applying a map-ID normalization during initial
extraction.

## Placed-entity record format

The ROM log describes the pointed-to sprite/overlord lists as three-byte
clusters:

| Byte within record | Meaning described in source | Notes |
| ---: | --- | --- |
| 0 | Y coordinate | Converted to pixel units later |
| 1 | X coordinate | Converted to pixel units later |
| 2 | Sprite or overlord type | Loads to sprite-type state at `$0E20,X` or overlord state at `$0B00,X` |

Overworld overlord encoding differs from dungeon entity records. The log says a
third-byte value greater than or equal to `$F3` is treated as an overlord; the
loader subtracts `$F3` to get the overlord index. Values below `$F3` are
treated as ordinary sprite types. Keep the raw byte and record type decision
separately so the original encoding remains auditable.

The list uses an `$FF` sentinel after the last cluster. The source log's
description does not fully specify every malformed/truncated-list edge case,
so a future parser should report missing termination explicitly rather than
silently reading to the end of the ROM.

These records are a placed-entity list, not the same thing as the sprite-type
statistics arrays below. The pointer array has an area index; the record list
has its own local record index; the third byte has an encoded sprite/overlord
type. Preserve all three identities separately.

## Per-sprite statistics

The ROM log says the following arrays are each `$F3` (243) bytes long, matching
the number of sprite types described by that log. The first four have arithmetic
ranges that follow directly from the stated start offsets and length:

| Start offset | Calculated inclusive end | Source description |
| --- | --- | --- |
| `$06B080` | `$06B172` | Unknown field; value is stored to WRAM `$0E40,X` |
| `$06B173` | `$06B265` | Initial HP, stored to `$0E50,X` |
| `$06B266` | `$06B358` | Damage the sprite can cause to Link |
| `$06B359` | `$06B44B` | Possibly a main palette index, stored to `$0E60,X` |

The same log lists another value at `$06B4CC,X` and a further range beginning
at `$06B8F1`, but the comments shown there do not describe their semantics or
length sufficiently. There is an unexplained gap between the calculated end
of the fourth array (`$06B44B`) and the next reported offset (`$06B4CC`).
Do not assume the gap is padding or another table without tracing the source
and the code that consumes it.

The RAM log and code labels can supply evidence for field meanings, but the
initial export should retain raw bytes and source offsets even for unknown
fields. “Unknown” is valid metadata; a guessed label is not.

## Suggested source-auditable model

A future extractor should produce separate records:

- `area_pointer`: story state, area index, pointer-entry file offset,
  original pointer bytes/expression, and resolved list offset when verified.
- `placed_entity`: area/story-state reference, list-local index, record
  source offset, raw Y byte, raw X byte, raw type byte, decoded
  sprite-vs-overlord classification, and sentinel/termination status.
- `sprite_stat`: raw sprite type index, table name, source offset, raw byte,
  source description, and interpretation status (`unknown`, `inferred`,
  `verified`).

For pointer targets, record the original two-byte value and the decoding method
separately from the target file offset. Do not resolve pointers by pretending
that they are direct LoROM CPU addresses; confirm the base/relative-pointer
rules in the actual loading code first.

## Validation gates

1. Verify pointer widths, address base, and story-state table selection in the
   loading code, then compare each pointer entry with a local clean US ROM.
2. Decode lists only after the pointer scheme is confirmed. Check the sentinel
   and retain all raw triples so entity ordering is stable.
3. Confirm the `$F3` threshold and overlord-index transformation at the
   consumer before creating semantic sprite/overlord IDs.
4. Verify each statistics array's length and index domain against the loading
   sites. Explain the unlabelled `$06B4CC` and `$06B8F1` ranges before
   treating them as complete tables.
5. Keep ROM-derived byte slices local and out of Git; synthetic records are
   sufficient for initial parser tests.

This is documentation only. It does not read or write ROM bytes and does not
claim that overworld entity extraction is implemented.
