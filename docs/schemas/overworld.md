# Overworld data discovery: high/low screen payloads

Status: **Phase 1 discovery note; not a completed overworld schema or extractor.**
This records the storage layout visible in the pinned Asar source without
claiming to decode the underlying map data.

## Source layout

The pinned
[`Bank0B.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Bank0B.asm#L3-L39)
labels the bank as overworld map data and starts the source-mapped region at
file offset `$058000` (`org $0B8000` in LoROM CPU address space). For example:

| Source label | File offsets in comments | Declared payload size | `incbin` path |
| --- | --- | ---: | --- |
| `OverworldMap32_Screen00_High` | `$058000–$058003` | `0x0004` | `bin/ow/screen00-h.bin` |
| `OverworldMap32_Screen00_Low` | `$058004–$0580D5` | `0x00D2` | `bin/ow/screen00-l.bin` |
| `OverworldMap32_Screen01_High` | `$0580D6–$0580D9` | `0x0004` | `bin/ow/screen01-h.bin` |
| `OverworldMap32_Screen01_Low` | `$0580DA–$0581C1` | `0x00E8` | `bin/ow/screen01-l.bin` |
| `OverworldMap32_Screen02_High` | `$0581C2–$058237` | `0x0076` | `bin/ow/screen02-h.bin` |
| `OverworldMap32_Screen02_Low` | `$058238–$058315` | `0x00DE` | `bin/ow/screen02-l.bin` |

The comments' inclusive ranges agree with their stated lengths: for example,
`$058000–$058003` is four bytes. That makes the source comments useful for
building a byte-location inventory, but does not explain the encoding.

A second source region starts in
[`Bank0C.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Bank0C.asm#L3-L57)
at file offset `$060000` (`org $0C8000`). It contains more of the same
`OverworldMap32_ScreenXX_High/Low` naming pattern; its source order is not a
simple ascending sequence of screen tokens (the displayed section moves from
`Screen64` to `Screen25`). Do not use physical source order as the screen ID.

## Important unknowns

- The `High` and `Low` suffixes identify two separate source payloads, but
  the cited data declarations alone do not establish their exact bit layout,
  decompression rules, or relationship to author-facing tile layers.
- The roadmap calls for an overworld map inventory, but these labels alone do
  not prove the final number of editable maps or how map IDs should be exposed
  through the authoring API.
- The tracked tree at pinned disassembly revision
  `347c23f9fc019c72d32da537c9cb235f468d021d` does not contain the referenced
  `bin/ow/*.bin` payloads. The source provides their include paths and size
  comments, but those binary files are not present as ready-made fixtures.

## Suggested extraction inventory

Begin with a source-grounded inventory rather than interpreting the payload:

| Field | Meaning |
| --- | --- |
| `screen_token` | Hex token from `ScreenXX`, preserved as source text |
| `high_label` / `low_label` | Exact pair of source labels |
| `high_source_path` / `low_source_path` | Exact `incbin` paths |
| `high_file_offset` / `low_file_offset` | File locations stated in source comments |
| `high_size_bytes` / `low_size_bytes` | Sizes stated in source comments |
| `source_revision` | Pinned disassembly revision used to create the inventory |
| `payload_available` | Whether the corresponding local payload or ROM-derived fixture exists |
| `decoder_status` | Explicit state such as `unverified`, `decoded`, or `fixture-checked` |

Retain the exact source label and path even if a normalized screen identifier
is added later. Leave semantic layer fields out until the consumer code and a
verified fixture establish what the bytes mean.

## Validation gates

1. [x] Inventory all `OverworldMap32_ScreenXX_High/Low` declarations from the
   pinned source without assuming the source order is numeric.
2. [x] Validate that every source-local screen token has exactly one High and
   one Low declaration; the CLI reports missing or duplicate members.
3. Reconcile the source tokens with YAZE/z3ed's output and the roadmap's intended
   map count using a locally supplied clean US ROM.
4. Validate every source-reported offset and size against a local ROM or
   generated local fixture before decoding the payload.
5. Only document tiles, layers, entrances, palettes, or warps once their
   representations have been traced to consumer code and tests.

This documentation does not read, copy, or modify ROM bytes.



## Hole and entrance lookup tables

The same pinned
[`Bank1B.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Bank1B.asm#L411-L490)
contains small, source-labelled tables used to map overworld hole/door
locations to entrance IDs. These are separate from the `ScreenXX_High/Low`
payloads above.

### Holes

`Pool_Overworld_Hole` spans file offsets `$0DB800–$0DB85F` (96 bytes):

| Label | Start offset | Count / width | Description in source |
| --- | --- | --- | --- |
| `.map16` | `$0DB800` | 19 words | Map16 coordinates for holes |
| `.area` | `$0DB826` | 19 words | Overworld area numbers paired with the coordinates |
| `.entrance` | `$0DB84C` | 20 bytes | Entrance IDs used after a hole match or fallback |

The count difference is intentional in the visible consumer flow: the routine
scans the 19 Map16/area pairs, but if none match it selects byte offset
`$0026`, divides by two, and reads the twentieth `.entrance` byte. The
source comment says this fallback sends Link to the Chris Houlihan room; its
table byte is `$82`. Keep the fallback entry separate from the 19 ordinary
coordinate/area rows rather than inventing a twentieth coordinate.

### Doors and entrances

`Pool_Overworld_Entrance` spans `$0DB8BF–$0DBBF3` (0x335 bytes), divided into
five arrays:

| Label | Start offset | Count / width | Purpose established by source |
| --- | --- | --- | --- |
| `.ValidDoorTypes_low` | `$0DB8BF` | 44 words | Low half of accepted door-tile type pairs |
| `.ValidDoorTypes_high` | `$0DB917` | 44 words | High half of the same accepted pairs |
| `.Screens` | `$0DB96F` | 129 words | Screen/area values used to locate a door entrance |
| `.TileIndex` | `$0DBA71` | 129 words | Tile-index values paired with `.Screens` |
| `.ID` | `$0DBB73` | 129 bytes | Entrance ID returned for the matching table slot |

The entrance-check routine compares both halves of a door tile type against the
44 `.ValidDoorTypes` pairs. It then searches `.Screens` and `.TileIndex` in
parallel; on a match, it halves the byte offset to index the one-byte `.ID`
array. This supports an inventory with a stable zero-based table slot and a
separate stored entrance-ID byte.

Do not conflate the array slot with the stored ID: source comments label
`.ID` slots from `0x00` upward while the byte comments name values such as
`ENTRANCE 01`. Preserve the slot, original byte, and source comment separately
until the editor's ID convention is independently verified.

The relevant consumers are visible in
[`Bank1B.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Bank1B.asm#L451-L474)
for hole entry and
[`Bank1B.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Bank1B.asm#L990-L1055)
for door/entrance matching.

### Extraction requirements

Keep these structures in a separate raw inventory from decoded overworld tile
layers. Before exposing entrance CRUD operations:

1. Preserve every source table slot and its exact source label/address.
2. Compare the three hole arrays and the three parallel entrance arrays with a
   locally supplied clean US ROM; assert the documented counts and widths.
3. Test the hole fallback path separately from ordinary coordinate matches.
4. Verify whether entrance IDs are one-based values, table-slot indexes, or a
   distinct domain by following the code that consumes `$010E`.
5. Keep ROM-derived byte fixtures local and out of Git.

This remains source-backed discovery, not a complete overworld editor schema.
No ROM bytes are read or modified by this documentation.


## Committed source payload inventories

The source metadata from both physical banks is now captured in registered
JSON files: `overworld-payloads-bank0b.json` (164 declarations from
`Bank0B.asm`) and `overworld-payloads-bank0c.json` (84 declarations from
`Bank0C.asm`). The records preserve exact labels, `incbin` paths, source lines,
source-reported inclusive offsets, declared sizes, computed ends, and match
flags. They do not include any map bytes or treat High/Low as fully understood
semantic tile layers.

The inventory exposes the current offset comments' anomalies rather than
repairing them: Bank0B has one missing range on `Screen4F_High` and size/range
mismatches on `Screen42_Low` and `Screen61_Low`; Bank0C has a mismatch on
`Screen88_Low`. These must be reconciled with the consumer code and a local
clean US ROM before using these ranges as a writable schema. The pinned source
tree has no tracked `bin/ow/*.bin` payloads.

See [the committed extracted-data guide](../extracted-data.md) for exact
counts, anomalies, and commands to regenerate the two JSON inventories.

Run the source-local pair-integrity check after regenerating either inventory:

```bash
uv run zelda-suite validate-overworld-payload-pairs \
  data/extracted/overworld-payloads-bank0b.json \
  data/extracted/overworld-payloads-bank0c.json
```

The report currently confirms 82 pairs in Bank0B and 42 in Bank0C (124 total).
It validates labels and metadata shape only; it does not reconcile annotated
offsets with a local ROM or decode the payload binaries.

## Source-level layout audit

Run `audit-overworld-payload-layout` after regenerating the source inventories:

```bash
uv run zelda-suite audit-overworld-payload-layout \
  data/extracted/overworld-payloads-bank0b.json \
  data/extracted/overworld-payloads-bank0c.json \
  --output /tmp/overworld-payload-layout-audit.json
```

This report pins the 124 screen pairs and exposes their High/Low declaration
sizes and source-annotated offsets. On the current revision it records three
range-size discrepancies and one missing range annotation. For known ranges,
the High end and Low start are adjacent according to the comments; Screen4F
High is the one pair whose candidate adjacency cannot be calculated.

The source log describes High and Low as compressed high-byte and low-byte
streams of Map32 words, and `Bank0A.asm` calls
`Overworld_LoadAndBuildScreen_long` to load/build Map32 and subsequent Map16
data. This is source context, not a payload decoder. The pinned repository does
not track the included `bin/ow/*.bin` payloads, and no local ROM was read.
The audit reports this explicitly; actual decoding, an editable map-layer
schema, and ROM-offset reconciliation remain open.

See the [versioned report schema](./overworld-payload-layout-audit.schema.json).
