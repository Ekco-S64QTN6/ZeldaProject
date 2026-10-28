# Overworld hidden-item data: source discovery

Status: **Phase 1 source discovery; no local-ROM pointer/byte verification or editable record export yet.**
This note captures the table layout described by the pinned disassembly and its
ROM-analysis log. It is not an extraction implementation.

## Source-reported layout

The pinned
[`Bank1B.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Bank1B.asm)
declares `OverworldData_HiddenItems` as the overworld secrets pointer table at
file offset `$0DC2F9`. Its adjacent source comments describe the region as
`$0DC2F9–$0DC3F8`; the table has 0x80 (128) entries expressed as `dw`
(two-byte words). Each word points to source labels with names such as
`OverworldData_HiddenItems_Screen_00`. Repeated pointers are expected in the
source: multiple area indices may use the same hidden-item list.

The pinned
[`Logs/Zelda_3_ROM.log`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Logs/Zelda_3_ROM.log)
describes the surrounding region this way:

| Region | File-offset range (inclusive) | Source description |
| --- | --- | --- |
| Area pointer table | `$0DC2F9–$0DC3F8` | 0x80 two-byte pointers |
| Hidden-item records | `$0DC3F9–$0DC89B` | Three-byte records: two-byte Map16 coordinate followed by one-byte value |
| Replacement Map16 values | `$0DC89C–$0DC8A3` | Four two-byte replacement values |

The log lists the record-value bytes it observed as `$00–$16` and `$80`,
`$82`, `$84`, `$86`, `$88`. Those are documented values, not yet a full
semantic item enum: the authoring model must not assign human-readable item
names without cross-referencing the relevant handlers and validating them in
the game.

## Source-level byte accounting and reader behavior

The inclusive range `$0DC3F9–$0DC89B` contains `0x4A3` bytes (1,187 bytes).
Counting the pinned `Bank1B.asm` declarations in that region yields 351
`dw $xxxx : db $yy` entries (three bytes each) and 67 standalone
`dw $FFFF` words (two bytes each). Their declared widths sum to
`351 × 3 + 67 × 2 = 1,187` bytes, exactly matching the source-reported range.
The earlier “two-byte tail” calculation incorrectly treated the whole region
as a flat array of three-byte entries and did not account for sentinel words.

The pinned `Overworld_RevealSecret` consumer provides the source-level read
pattern. It indexes the pointer table with the area index multiplied by two,
loads the selected pointer, advances through candidate entries in three-byte
strides, and compares the leading word with `$FFFF` to stop. For a matching
coordinate it advances two more bytes and reads the one-byte value. This
describes the source routine; it does not independently verify bytes in a
locally supplied ROM.

There are 80 distinct `OverworldData_HiddenItems_Screen_XX` target labels,
but only 67 `dw $FFFF` declarations. Thirteen label blocks have no local
terminator before the next screen label. Because the reader stops on the
`$FFFF` word rather than on a source label or brace boundary, a label block
must not automatically be treated as a complete, independent record array.

**Remaining gate:** preserve pointer expressions and the source-level reader
rule, but do not claim ROM-verified pointer targets, record offsets, per-area
record counts, or value semantics until the source layout is compared with a
trusted local US ROM.

## Proposed raw extraction record

A first-pass, audit-oriented record can keep the observed fields without
guessing their semantics:

| Field | Meaning |
| --- | --- |
| `area_index` | Pointer-table index, integer `0–127` |
| `pointer_entry_file_offset` | Entry location, `0x0DC2F9 + area_index * 2` |
| `pointer_expression` | Original `dw` expression retained verbatim |
| `target_label` | Parsed target label; not a resolved file offset |
| `source_revision` | Pinned disassembly revision `347c23f9fc019c72d32da537c9cb235f468d021d` |
| `record_file_offset` | Nullable until pointer decoding is verified |
| `records` | Ordered raw records, preserving the original two-byte coordinate and one-byte value |
| `unparsed_tail_bytes` | Any bytes not explained by verified record structure |
| `replacement_map16_values` | Four raw two-byte values from the documented replacement region |

The Map16 coordinate is a little-endian two-byte value only if confirmed from
the source consumer/ROM representation; preserve raw bytes before promoting it
to an integer or an editor coordinate. The log calls it a Map16 coordinate, but
this discovery note does not establish the in-memory byte order or coordinate
transform used by a future API.

## Validation gates

1. Locate `OverworldData_HiddenItems` and its target labels in the pinned
   source. Preserve the exact table expressions and source revision.
2. Source review now identifies `Overworld_RevealSecret` as the reader: it
   advances by three bytes and stops on a leading `$FFFF` word. Regression
   tests preserve this source pattern and the declaration-size accounting.
3. Compare all 128 pointer entries with their corresponding two-byte entries
   in a locally supplied clean US ROM; resolve bank-relative pointers using the
   verified runtime mapping, not assumptions about label addresses.
4. Determine the meaning of the value byte from the code that consumes it.
   Preserve unknown values as raw numbers in the meantime.
5. The source declarations account for the documented range as 351
   three-byte entries plus 67 two-byte sentinel words. Compare that layout
   against a trusted local US ROM and establish record grouping across source
   labels before asserting per-area counts or exposing CRUD operations.
6. Keep ROMs and partial ROM slices local. Tests should use synthetic byte
   fixtures or user-supplied local fixtures, never committed ROM data.

This note and its source-only regression coverage do not read, copy, or modify
ROM bytes.


## Export the source pointer table

The shared source-table parser can export the 128 two-byte pointer expressions
without resolving targets or decoding the hidden-item records:

```bash
uv run zelda-suite inspect-pointer-table \
  reference/AsarUSALTTPDisassembly/Bank1B.asm \
  OverworldData_HiddenItems \
  --table-offset '$0DC2F9' \
  --directive dw \
  --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d \
  --output /tmp/hidden-item-pointers.json
uv run zelda-suite validate-source-export /tmp/hidden-item-pointers.json
```

The parser's two-byte stride is checked against the pinned source table in CI.
The output validates the source expressions and entry locations only; the
pointed-to lists still require local-ROM verification before record extraction.


## Committed source pointer inventory

The version-1 metadata export at
`data/extracted/overworld-hidden-item-pointers.json` records the 128
`dw` expressions in this table at source offsets `$0DC2F9–$0DC3F8`. It is
registered under the name `overworld-hidden-item-pointers` and can be loaded
with `load_extracted_asset("overworld-hidden-item-pointers")`.

CI compares the committed records with `parse_dw_pointer_table()` output from
the pinned submodule. This validates table count, source expressions, source
line numbers, and the two-byte source entry stride. It does not resolve target
labels into file offsets or verify any of the pointed-to data against a local
ROM. The source-level byte accounting matches the documented range, but pointer
resolution, record bytes, and per-area grouping remain unverified against a
local ROM.
