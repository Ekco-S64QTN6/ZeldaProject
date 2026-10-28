# Overworld hidden-item data: source discovery

Status: **Phase 1 discovery; pointer decoding and record boundaries are not yet verified against a local ROM.**
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

## A size discrepancy to resolve

The stated hidden-item-record range has an inclusive size of `0x4A3` bytes
(1,187 bytes). That is not evenly divisible into three-byte records:
395 triples account for 1,185 bytes, leaving two bytes unexplained. This may
reflect a sentinel, alignment, or a discrepancy in the source log, but the
available text alone does not establish which.

**Do not derive a final record count from this range yet.** Before building a
parser, inspect the exact source labels and consumers, then compare the table
against a local clean US ROM. Record the unexplained bytes explicitly until
their purpose is verified.

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
2. Identify the code that reads an area pointer and iterates hidden-item
   records, including the actual termination condition.
3. Compare all 128 pointer entries with their corresponding two-byte entries
   in a locally supplied clean US ROM; resolve bank-relative pointers using the
   verified runtime mapping, not assumptions about label addresses.
4. Determine the meaning of the value byte from the code that consumes it.
   Preserve unknown values as raw numbers in the meantime.
5. Explain the two-byte tail discrepancy in the stated data range before
   asserting a record count or exposing CRUD operations.
6. Keep ROMs and partial ROM slices local. Tests should use synthetic byte
   fixtures or user-supplied local fixtures, never committed ROM data.

This is documentation only. No ROM bytes are read, copied, or modified.


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
ROM. The two-byte unexplained tail in the documented hidden-item record range
is still unresolved.
