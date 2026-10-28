# Overworld hidden-item data: source discovery

Status: **Phase 1 source layout and read-only verifier implemented; verification against the user's local ROM remains to be run. No editable item schema is claimed.**
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

**Remaining gate:** the new `zelda-suite verify-overworld-hidden-items ROM`
command computes the source record offsets, resolves each pointer expression
to a low-bank LoROM word, derives lists by the consumer's sentinel rule, and
checks the pointer/data bytes against a supplied local image. It has synthetic
regression coverage, but has not yet been run by the user against their ROM.
Do not call the result a canonical-ROM or provenance check; semantic value
meanings also remain unresolved.

## Proposed raw extraction record

A first-pass, audit-oriented record can keep the observed fields without
guessing their semantics:

| Field | Meaning |
| --- | --- |
| `area_index` | Pointer-table index, integer `0–127` |
| `pointer_entry_file_offset` | Entry location, `0x0DC2F9 + area_index * 2` |
| `pointer_expression` | Original `dw` expression retained verbatim |
| `target_label` | Parsed target label; the verifier calculates a candidate file offset from the source declaration widths |
| `source_revision` | Pinned disassembly revision `347c23f9fc019c72d32da537c9cb235f468d021d` |
| `record_file_offset` | Candidate file offset derived by the verifier; it is not trusted-ROM verified until a local byte comparison passes |
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
3. Run `zelda-suite verify-overworld-hidden-items "$ROM"` against the local
   image to compare 128 pointer words, 351 three-byte records, 67 sentinel words,
   and four replacement Map16 words. Review all mismatches without modifying
   source offsets speculatively.
4. The verifier derives the 128 area lists by scanning three-byte records until
   a leading `$FFFF` sentinel. Confirm the reported grouping against a trusted
   ROM before treating per-area record counts as validated data.
5. Determine the meaning of the value byte from the code that consumes it.
   Preserve unknown values as raw numbers in the meantime.
6. Keep ROMs and partial ROM slices local. Tests should use synthetic byte
   fixtures or user-supplied local fixtures, never committed ROM data.

The source parser and synthetic tests do not use a user's ROM. The verification
command reads a locally supplied ROM and writes only its JSON report; it never
changes, copies, or stores ROM bytes in the repository.


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


## Source-only layout report

The ROM-independent `zelda-suite inspect-overworld-hidden-items` command emits a versioned JSON report containing the pinned source's 128 pointer entries, 80 target-label offsets, 351 three-byte records, 67 two-byte sentinels, 128 sentinel-delimited area lists, and four replacement words.

```bash
uv run zelda-suite inspect-overworld-hidden-items \
  --output /tmp/overworld-hidden-item-source-layout.json
```

The output contract is documented in [`overworld-hidden-item-source-layout.schema.json`](./overworld-hidden-item-source-layout.schema.json). The command reads `reference/AsarUSALTTPDisassembly/Bank1B.asm` only; it neither opens a ROM nor writes to the asset registry. `rom_verified` and `semantic_values_decoded` remain `false`. Use the separate ROM verifier below before treating offsets or area grouping as confirmed against a game image.

## Read-only ROM verification command

The `verify-overworld-hidden-items` command can be run from the repository
root after the ROM variable is set as described in
[`real-rom-verification.md`](../real-rom-verification.md):

```bash
uv run zelda-suite verify-overworld-hidden-items "$ROM" \\
  --output /tmp/overworld-hidden-item-verification.json
```

The report format is described by
[`overworld-hidden-item-verification.schema.json`](./overworld-hidden-item-verification.schema.json).
It checks 550 expected byte spans and provides the source-derived record index
list for each of the 128 area pointers. The JSON's `provenance_verified` field
is deliberately false: matching known table declarations does not establish a
canonical ROM dump. Test against a real local image before accepting the
source-commented offsets as verified for that image.
