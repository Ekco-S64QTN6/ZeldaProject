# Receive-item metadata tables: source discovery

Status: **Phase 1 discovery; not a finalized item-ID schema.** The pinned
disassembly groups several arrays used by the receive-item routine. They are
good candidates for source-grounded extraction, but one set of item-index
comments disagrees with the consumer code and must be resolved before exposing
semantic item IDs.

## Source block and consumers

In the pinned
[`Ancilla/ancilla_init.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Ancilla/ancilla_init.asm#L546-L733),
the `Pool_AddReceiveItem` data block spans file offsets
`$04836C–$0485E7`. The next label, `AddReceivedItem`, begins immediately at
`$0485E8`. The consumer loads the incoming item index into `Y`, indexes
`.item_target_addr` and `.item_values`, writes to the specified address in
bank `$7E`, and then handles special item cases such as boots, flippers,
gloves, pendants, armor, and dungeon map/key items
([`AddReceivedItem` source](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Ancilla/ancilla_init.asm#L735-L885)).

The entire data block has an inclusive length of `0x27C` bytes (636 bytes).
The source-commented subtable starts and the lengths implied by the next label
are:

| Source label | Start offset | Length | Storage shape / source description |
| --- | --- | ---: | --- |
| `.y_offsets` | `$04836C` | 76 bytes (`0x4C`) | One byte per apparent item entry |
| `.x_offsets` | `$0483B8` | 76 bytes (`0x4C`) | One byte per apparent item entry |
| `.item_graphics_indices` | `$048404` | 76 bytes (`0x4C`) | One byte per entry; source comments name item IDs and graphics values |
| `.wide_item_flag` | `$048450` | 76 bytes (`0x4C`) | One byte per entry; preserve values without guessing bit semantics |
| `.properties` | `$04849C` | 76 bytes (`0x4C`) | One byte per entry; meanings need code-level verification |
| `.item_target_addr` | `$0484E8` | 152 bytes (`0x98`) | 76 little-endian words naming target addresses |
| `.item_values` | `$048580` | 76 bytes (`0x4C`) | One byte per entry; source comment says these are written to target addresses |
| `.item_masks` | `$0485CC` | 28 bytes (`0x1C`) | 14 two-byte masks, used separately for dungeon items |

The range and table widths above follow the labels and data declarations in
the pinned source. The runtime sets the bank byte to `$7E` before using a
target address, so `.item_target_addr` should be modeled as target-address
metadata, not as ROM pointers.

## Item-index comment discrepancy

The `.item_graphics_indices` declarations label entries from `0x00` through
`0x3F`, then resume with a comment labelled `0x41` and continue through
`0x4C`. That comment sequence skips `0x40`, but the table's declared byte
length is only `0x4C` (76 bytes), which, for a zero-based dense array, yields
positions `0x00–0x4B`.

The consumer code independently checks `CPY #$4B` for Pegasus boots, whereas
the `.item_graphics_indices` source comment labels the last `$38` byte as
`0x4C - BOOTS`. This is evidence of an inconsistency in source comments or
index labeling. **Do not silently shift indices or assume the comment labels
are the canonical item IDs.** Use the consumer behavior and a local clean ROM
to resolve the valid index domain before normalizing these tables.

Other consumer checks provide useful cross-references: the routine explicitly
handles flippers at `$1E`, gloves at `$1B`/`$1C`, pendants at
`$37–$39`, and boots at `$4B`. These checks support investigation but do not
on their own resolve every label in all parallel arrays.

## Preserve raw values before interpreting them

The source says negative entries in `.item_values` are not written to the
target location. Since the table stores bytes and the consumer branches on the
negative flag, keep each raw byte in the extracted record; do not replace
values such as `$FF`, `$FB`, or `$EC` with a guessed meaning until the
relevant usage and signed interpretation are documented.

Likewise, `.wide_item_flag` and `.properties` have names but not a complete
semantic contract in the table declaration alone. Keep their raw fields,
original source offsets, and source revision.

## Proposed extraction record

A source-auditable extraction should store one record per byte-sized entry,
plus a separate collection for the 14-word `.item_masks` table:

| Field | Meaning |
| --- | --- |
| `array_name` | Exact source label, such as `.item_values` |
| `table_index` | Zero-based index into the declared array, preserved as parsed |
| `file_offset` | Verified offset calculated from the source label start and element width |
| `raw_value` | Original byte or word value before semantic conversion |
| `source_comment_index` | Item index written in the comment, nullable and distinct from the table position |
| `source_comment` | Original per-entry comment, if present |
| `source_revision` | Pinned disassembly revision `347c23f9fc019c72d32da537c9cb235f468d021d` |

Retaining both `table_index` and `source_comment_index` makes the apparent
`0x40` gap explicit instead of silently normalizing it away. The authoring
API should consume resolved semantic IDs only after the discrepancy has been
explained and tests pin the interpretation.

## Validation gates

1. Parse the labels, element widths, and comments from the pinned source while
   preserving source order and raw values.
2. Compare each address/offset range and table length with the locally supplied
   clean US ROM before marking the inventory verified.
3. Trace the routines that index each table, particularly the index domain
   around `$3F–$4C`, and document any reserved or skipped values.
4. Add synthetic parser tests and local-ROM verification tests without
   committing ROM files or ROM-derived binary slices.

This is a source-backed discovery note only. It does not read or modify ROM
bytes and does not claim the item tables are editable yet.


## Committed raw table assets

The following three source-derived files are registered in
`data/extracted/manifest.json` and can be loaded by name with the shared asset
loader:

- `item-receipt-target-addresses` — 76 two-byte values beginning at `$0484E8`.
- `item-receipt-values` — 76 one-byte values beginning at `$048580`.
- `item-receipt-dungeon-masks` — 14 two-byte masks beginning at `$0485CC`.

They preserve the exact expressions and source positions from the pinned
`Ancilla/ancilla_init.asm` and are checked against `parse_data_table()` output
in CI. The first table records WRAM target addresses; they are not resolved ROM
pointers. The second table retains raw byte patterns including `$FF`, `$FB`,
and `$EC`; runtime handling such as skipping negative signed values is not
normalized into editorial item meanings. The third table stores the raw mask
words without inferring a full authoring API.

The `.item_graphics_indices` table and its missing comment index `$40` are
still an independent unresolved discovery issue; these three exports do not
claim to settle that discrepancy or provide a complete item schema.
