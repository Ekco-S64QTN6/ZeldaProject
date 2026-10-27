# Graphics and palette data: source discovery

Status: **Phase 1 inventory, not a graphics decoder or editable palette schema.**
The pinned disassembly documents some exact graphics ranges and palette lookup
tables, but these are different data types and must be extracted separately.
The references below are from revision
`347c23f9fc019c72d32da537c9cb235f468d021d`.

## Palette lookup tables

The pinned
[`Bank0E.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Bank0E.asm)
defines three neighboring data structures:

| Source label | Headerless file-offset range (inclusive) | Size | Source-described role |
| --- | --- | ---: | --- |
| `UnderworldPaletteSets` | `$075460–$075503` | `0xA4` bytes = 41 groups × 4 bytes | Dungeon palette indices, applied to WRAM `$0AB6`, `$0AAC`, `$0AAD`, `$0AAE` |
| `OverworldPaletteSet` | `$075504–$07557F` | `0x7C` bytes = 31 groups × 4 bytes | Overworld palette-selection metadata; comments mention `$0AB4`, `$0AB5`, and `$0AB8` |
| `OverworldSpritesPaletteSet` | `$075580–$0755A7` | `0x28` bytes = 20 pairs | Overworld sprite palette indices, used to set `$0AAD` and `$0AAE` |

The inclusive lengths match the source declarations' groupings. The table values
are palette **indices / selectors**, not palette RGB color data. Keep these
lookup structures separate from actual palette bytes, tileset graphics, and
runtime palette state.

The routine `Overworld_LoadPalettes` follows the tables in
[`Bank0E.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Bank0E.asm):
it loads several values from `OverworldPaletteSet` into WRAM palette selectors
and uses a separate index path to read another value into `$0AAD`. Because the
fourth byte is accessed with a different indexing path, do not assume all four
columns have one identical index domain just because the data is stored in
four-byte groups. Preserve row index, within-row byte index, and raw value
separately until the consumer behavior has been fully traced.

## Map16 to Map8 conversion data

The pinned
[`Logs/Zelda_3_ROM.log`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Logs/Zelda_3_ROM.log)
identifies `$078000` as the start of the Map16-to-Map8 conversion data. It
describes the conversion entries as groups of eight bytes, representing four
Map8 tiles for one Map16 tile.

The cited log entry does **not** specify the full length of this region. Treat
`$078000` as a source-reported start, not a license to infer a table end or
count. Before exposing tile conversion as editor data, locate the consuming
code and establish the actual extent, indexing order, and per-tile bit fields.

## Source-reported graphics regions

The ROM log also identifies these graphics payloads:

| Headerless file-offset range | Size | Source description | Caveat |
| --- | ---: | --- | --- |
| `$070000–$070FFF` | `0x1000` bytes | Uncompressed BG3 variable-width-font graphics | Font glyph pixels, not message text streams |
| `$080000–$086FFF` | `0x7000` bytes | 4bpp graphics sets for Link's animations | Graphics payload; frame/tile mapping still needs to be traced |
| `$087000–$08B7FF` | `0x4800` bytes | Uncompressed 3bpp graphics sets | Do not assume every graphics block is compressed |
| `$0C3520` | Start offset only | Compressed 2bpp menu-screen graphics (bug-catching net, medallions, etc.) | Extent not stated in that log entry |
| `$0C3953` | Start offset only | Compressed 2bpp menu-screen graphics (magic mirror, Book of Mudora, etc.) | Extent not stated in that log entry |

The first range corresponds to `binary_files/font_GFX.bin` in the pinned
[`Bank0E.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Bank0E.asm).
The log's “uncompressed” and bit-depth descriptions are important distinctions:
some graphics data is compressed, while other assets are stored uncompressed
or in a proprietary 3bpp form. A future adapter must select the right codec
based on a verified asset definition, not based on the assumption that all
graphics are compressed.

## Suggested source-auditable inventory

Before decoding assets, inventory each region with at least:

| Field | Purpose |
| --- | --- |
| `source_label` | Exact label, if one exists in the pinned source |
| `file_offset_start` / `file_offset_end` | Source-confirmed byte range; end remains null when unknown |
| `declared_size_bytes` | Source or verified local-ROM size, kept separate from calculated size |
| `data_kind` | `palette_index`, `palette_color`, `tile_conversion`, `font_gfx`, `graphics_2bpp`, `graphics_3bpp`, `graphics_4bpp`, or `unknown` |
| `compression` | Explicit `compressed`, `uncompressed`, or `unknown` state |
| `entry_width` / `group_width` | Byte grouping evidenced by the source |
| `consumer` | Routine or WRAM target proving how the bytes are used |
| `source_revision` | Pinned disassembly revision |
| `decoder_status` | `inventory-only`, `decoded`, or `fixture-checked` |

Do not generate a semantic palette name from an index alone. The same palette
selector may mean different things depending on BG/sprite context and the
consumer's index path.

## Validation gates

1. Verify all range boundaries and grouping arithmetic against the local clean
   US ROM before extracting bytes.
2. Trace the consumers of palette tables to identify each index domain and how
   it maps to WRAM; compare behavior with source comments.
3. Determine the Map16 conversion table's full extent and entry ordering from
   consuming code before implementing `setOverworldTile` or tile conversion.
4. Verify bit depth and compression for every asset family and test lossless
   decode/re-encode round trips with local fixtures.
5. Keep ROM files and extracted binary payloads local. No partial ROM slices or
   copyrighted assets are needed for source-inventory tests.

This note is documentation only. It neither extracts nor edits graphics, palettes,
or ROM bytes.
