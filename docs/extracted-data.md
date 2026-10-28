# Committed source-derived data

The `data/extracted/` directory contains auditable source-derived JSON exports. These exports contain source declarations and interpreted numeric literals; they are not ROM byte slices and they do not constitute a complete global item catalog.

## Falling-prize parallel tables

Five exports now cover the parallel lookup arrays used by `Pool_AddPendantOrCrystal` in the pinned `Ancilla/ancilla_init.asm` source revision `347c23f9fc019c72d32da537c9cb235f468d021d`.

| Export | Source label | File-offset range | Directive | Entries |
| --- | --- | --- | --- | ---: |
| `falling-prize-item-values.json` | `.item_values` | `$048B90–$048B96` | `db` | 7 |
| `falling-prize-fall-heights.json` | `.fall_height` | `$048B97–$048B9D` | `db` | 7 |
| `falling-prize-y-offsets.json` | `.y_offsets` | `$048B9E–$048BAB` | `dw` | 7 |
| `falling-prize-x-offsets.json` | `.x_offsets` | `$048BAC–$048BB9` | `dw` | 7 |
| `falling-prize-delay-timers.json` | `.delay_timers` | `$048BBA–$048BC0` | `db` | 7 |

Every export records the table index, calculated file offset, source line, local source label, original expression, numeric literal, and pinned revision. The same index domain links the item value to its fall-height, coordinate offsets, and delay timer. Keep the raw values and separate table meanings; do not merge them into a guessed global item schema.

## Reproduce and review

From the repository root, generate each export to a temporary path:

```bash
uv run zelda-suite inspect-data-table reference/AsarUSALTTPDisassembly/Ancilla/ancilla_init.asm .item_values --table-offset '$048B90' --directive db --parent-label Pool_AddPendantOrCrystal --end-label .fall_height --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d --output /tmp/falling-prize-item-values.json
uv run zelda-suite inspect-data-table reference/AsarUSALTTPDisassembly/Ancilla/ancilla_init.asm .fall_height --table-offset '$048B97' --directive db --parent-label Pool_AddPendantOrCrystal --end-label .y_offsets --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d --output /tmp/falling-prize-fall-heights.json
uv run zelda-suite inspect-data-table reference/AsarUSALTTPDisassembly/Ancilla/ancilla_init.asm .y_offsets --table-offset '$048B9E' --directive dw --parent-label Pool_AddPendantOrCrystal --end-label .x_offsets --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d --output /tmp/falling-prize-y-offsets.json
uv run zelda-suite inspect-data-table reference/AsarUSALTTPDisassembly/Ancilla/ancilla_init.asm .x_offsets --table-offset '$048BAC' --directive dw --parent-label Pool_AddPendantOrCrystal --end-label .delay_timers --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d --output /tmp/falling-prize-x-offsets.json
uv run zelda-suite inspect-data-table reference/AsarUSALTTPDisassembly/Ancilla/ancilla_init.asm .delay_timers --table-offset '$048BBA' --directive db --parent-label Pool_AddPendantOrCrystal --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d --output /tmp/falling-prize-delay-timers.json
```

Validate the exports and compare them with the reviewed versions under `data/extracted/`. The CLI refuses to overwrite an existing output file, so generated outputs should be created in a temporary directory before a manual update.

## Validation and limits

CI loads all five committed exports through `load_source_export()` and compares their entry lists with `parse_data_table()` output from the pinned submodule. All tables must contain seven entries, but widths differ: `db` entries are one byte and `dw` entries two bytes. These tests validate source metadata and entry arithmetic; they do not verify the source offsets against a local ROM image.

The `AddPendantOrCrystal` values are used by a specific falling-prize routine. They should not be treated as the complete chest, shop, overworld-secret, or inventory item tables.


## Text dictionary pointer table

`data/extracted/text-dictionary-pointers.json` records the 98 `dw` expressions
in `DictionaryPointers` from `Bank0E.asm` at pinned revision
`347c23f9fc019c72d32da537c9cb235f468d021d`.

- Source file-offset range: `$074703–$0747C6`.
- Entry width/count: 98 two-byte `dw` expressions.
- Source indices: `$00–$61`, including `DictionaryEntries_endOfTable` at index `$61`.
- Each row retains the symbolic target expression; target file offsets are not resolved.

This table is part of the game's encoded text system. Adjacent pointer values
are used as bounds for variable-length dictionary fragments. The export records
the pointer declarations only; it does not decode dictionary bytes, decode
message streams, or translate encoded tokens into display text.

To regenerate the export from the pinned submodule:

```bash
uv run zelda-suite inspect-data-table \
  reference/AsarUSALTTPDisassembly/Bank0E.asm \
  DictionaryPointers \
  --table-offset '$074703' \
  --directive dw \
  --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d \
  --output /tmp/text-dictionary-pointers.json
uv run zelda-suite validate-source-export /tmp/text-dictionary-pointers.json
diff -u data/extracted/text-dictionary-pointers.json /tmp/text-dictionary-pointers.json
```

CI checks that all 98 records match the parsed pinned source exactly. The
source-derived JSON is metadata only; no message, dictionary, or ROM bytes are
copied into the project.

## Text dictionary fragment inventory

`zelda-suite inspect-text-dictionary` links the 98 symbolic entries in
`DictionaryPointers` to their corresponding `DictionaryEntries` labels.
The inventory is committed at
`data/extracted/text-dictionary-fragments.json`, pinned to
`347c23f9fc019c72d32da537c9cb235f468d021d`.

The inventory stores source metadata only:

- Pointer index, pointer-entry file offset, and raw symbol expression.
- Matching local fragment label, source line, and source-annotated file offset.
- Distance to the next fragment label, data directive width/count, and declared byte count.
- A comparison flag indicating whether the annotated extent agrees with the directive length.

It does not store fragment byte values or text comments, and it does not resolve a
source symbol by reading ROM memory. The JSON export is schema-validated by the
source asset loader.

Reproduce it with:

```bash
uv run zelda-suite inspect-text-dictionary \
  reference/AsarUSALTTPDisassembly/Bank0E.asm \
  --pointer-table-offset '$074703' \
  --data-offset '$0747C7' \
  --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d \
  --output /tmp/text-dictionary-fragments.json
uv run zelda-suite validate-source-export /tmp/text-dictionary-fragments.json
diff -u data/extracted/text-dictionary-fragments.json /tmp/text-dictionary-fragments.json
```

### Known source-layout discrepancy

The `.You` fragment is annotated at `$0748D6`, with `.endOfTable` at
`$0748D8`, so its source-comment extent is two bytes. The same source declares
`dw $18, $28, $2E`, which implies six bytes. The inventory preserves both facts
and sets `source_extent_matches_directive=false`; it does not choose which
annotation is wrong or claim that binary offsets have been validated.


## Text dictionary fragment inventory

`data/extracted/text-dictionary-fragments.json` joins the 98 symbolic entries
in `DictionaryPointers` to fragment labels in `DictionaryEntries`. Each record
contains the pointer index and entry offset, original target expression,
fragment label and source line, annotated source file offset, the next label's
offset, the extent implied by those labels, and the directive/element count
declared in source. It intentionally omits the actual encoded fragment bytes
and any decoded text.

To regenerate the metadata from the pinned submodule:

```bash
uv run zelda-suite inspect-text-dictionary \
  reference/AsarUSALTTPDisassembly/Bank0E.asm \
  --pointer-table-offset '$074703' \
  --data-offset '$0747C7' \
  --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d \
  --output /tmp/text-dictionary-fragments.json
uv run zelda-suite validate-source-export /tmp/text-dictionary-fragments.json
diff -u data/extracted/text-dictionary-fragments.json /tmp/text-dictionary-fragments.json
```

The current source declares 98 pointer targets, including `.endOfTable` at
`$0748D8`. The inventory preserves one notable mismatch: `.You` begins at
`$0748D6` and is followed by `.endOfTable` two bytes later, but its source
directive is `dw` with three values (six declared bytes). This is reported as
`source_extent_matches_directive: false`; no attempt is made to repair or
reinterpret that source declaration. Validate this region against a clean local
US ROM and the actual message decoder before using it as a writable schema.

The JSON shape is described by
[the dictionary fragment inventory schema](./schemas/dictionary-inventory-export.schema.json).
CI checks that the committed inventory equals the metadata parsed from the
pinned source, including the flagged extent discrepancy.

## Source text message index

`data/extracted/text-message-index.json` indexes the 397 source labels across
`Message_Data` in `Bank1C.asm` and `Message_DataExtra` in `Bank0E.asm` from
pinned revision `347c23f9fc019c72d32da537c9cb235f468d021d`. It contains message
IDs, source labels/lines, source offset comments, sequential source-derived
offsets calculated from declared directive lengths, and declared byte counts.
It intentionally does not include encoded message bytes or the source comments
that render human-readable dialogue.

The main block has 359 messages and its 32,554 declared bytes match the annotated
range exactly. Six source offset annotations disagree with the sequential
source-derived offsets; three of those annotations have malformed digit lengths.
The index preserves the original annotation and records the sequential offset
separately rather than correcting the disassembly.

The extra block has 38 messages. It contains no per-message offset comments, so
its message starts are inferred from the block start and preceding source
directive byte counts. Those declarations total 3,809 bytes, one byte less than
the annotated 3,810-byte block range. This is left as an explicit block-size
mismatch pending a trusted local-ROM check.

Regenerate the index with:

```bash
uv run zelda-suite inspect-text-messages \
  --block reference/AsarUSALTTPDisassembly/Bank1C.asm Message_Data '$0E0000' '$0E7F29' \
  --block reference/AsarUSALTTPDisassembly/Bank0E.asm Message_DataExtra '$075F40' '$076E21' \
  --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d \
  --output /tmp/text-message-index.json
uv run zelda-suite validate-source-export /tmp/text-message-index.json
diff -u data/extracted/text-message-index.json /tmp/text-message-index.json
```

The index is a metadata inventory, not a decoder or edit-ready text model.
Message-pointer construction, decoder control-token semantics, and actual
ROM verification remain separate roadmap tasks.


## Named asset registry

`data/extracted/manifest.json` registers the committed exports under stable
names. Use the named asset loader from the repository root:

```python
from zelda_suite.extract import list_extracted_assets, load_extracted_asset

assets = list_extracted_assets()
message_index = load_extracted_asset("text-message-index")
dictionary = load_extracted_asset("text-dictionary-fragments")
```

The registry records each relative filename, validated export format, source
revision, record count, subsystem, and description. The loader rejects
unregistered names, unsafe filenames, format/revision/count mismatches, and
invalid source export payloads. See the
[named asset loader guide](./asset-loader.md) and
[registry schema](./schemas/asset-registry.schema.json).

## SpriteActive3 handler dispatch

`data/extracted/sprite-active3-dispatch.json` indexes the 68 `dw` entries in
`SpriteActive3_Table` from pinned `Bank1E.asm` revision
`347c23f9fc019c72d32da537c9cb235f468d021d`. It covers the actual sprite type
IDs `$79–$BC`; each record keeps the source ID and zero-based table slot as
separate fields. Duplicate handler labels are preserved because distinct sprite
types intentionally alias some implementations.

The two-byte entry offsets span `$0F0B33–$0F0BBA`. Each source comment also
contains a short handler address annotation; that annotation is stored as text
and is not treated as a resolved ROM file offset.

Regenerate it with `zelda-suite inspect-sprite-dispatch` as documented in
[`sprite-dispatch.md`](./schemas/sprite-dispatch.md). The record contract is
defined by the [sprite-dispatch export schema](./schemas/sprite-dispatch-export.schema.json).


## Music track pointer index

`data/extracted/music-track-index.json` indexes the 35 entries under
`base SONG_POINTERS` in `Bank1B.asm` from pinned source revision
`347c23f9fc019c72d32da537c9cb235f468d021d`. Its source file offsets cover
`$0D8004–$0D8049`; each pointer entry is two bytes and has a source comment
index from `$01` through `$23`.

The export preserves all 15 empty `$0000` entries and four aliases to earlier
song labels. A zero-based table index is stored alongside the source-comment
track index, and every row retains the original expression, source line,
pointer-entry offset, and source revision. The table is registered under the
name `music-track-index` and can be loaded with
`load_extracted_asset("music-track-index")`.

Regenerate and compare it using the CLI in
[the audio discovery note](./schemas/audio.md). No song payload bytes are
included, and no source pointer is treated as an independently verified SPC
RAM address. The payload files are absent from the pinned submodule, so the
table is metadata-only and does not make audio rebuilding available.


## Music payload source inventory

`data/extracted/music-payload-inventory.json` inventories the 15 source-labeled
`incbin` declarations in `Bank1B.asm` under `bin/music/`. It is registered
as `music-payload-inventory` and loaded through the same named asset API.

The records preserve the exact include path, label, source line, source-commented
inclusive ROM file range, explicit `Size:` annotation when present, computed
end when a source start and declared size are both available, and the comparison
result when a range and declared size can be compared. The twelve main-song
entries include explicit size annotations and agree with their source ranges.
The three auxiliary entries have range comments but no inline size annotation;
those size/comparison fields remain null, which distinguishes source statements
from arithmetic inferred from their comments.

To reproduce it, run the existing `inspect-incbin` command shown in
[the audio discovery note](./schemas/audio.md), then validate and diff the JSON.
The command never opens the `incbin` targets; the pinned submodule does not track
the `bin/music/` payload files.


## Overworld hidden-item pointer table

`data/extracted/overworld-hidden-item-pointers.json` records all 128
`dw` expressions under `OverworldData_HiddenItems` in pinned
`Bank1B.asm` revision `347c23f9fc019c72d32da537c9cb235f468d021d`. Entries
span source file offsets `$0DC2F9–$0DC3F8`, beginning at `$0DC2F9` and
advancing by two bytes per pointer. The committed export preserves source
expressions, line numbers, table indices, pointer-entry offsets, and source
revision, and it is registered as `overworld-hidden-item-pointers`.

This is strictly a pointer-table asset. It does not resolve targets to binary
file offsets, decode any hidden-item list, infer a final record count, or
interpret the one-byte value semantics. The documented records range
`$0DC3F9–$0DC89B` is `0x4A3` bytes—two bytes beyond 395 three-byte records.
That discrepancy remains open pending consumer/source analysis and comparison
with a local clean US ROM.

Regenerate the source metadata with:

```bash
uv run zelda-suite inspect-pointer-table \
  reference/AsarUSALTTPDisassembly/Bank1B.asm \
  OverworldData_HiddenItems \
  --table-offset '$0DC2F9' \
  --directive dw \
  --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d \
  --output /tmp/overworld-hidden-item-pointers.json
uv run zelda-suite validate-source-export /tmp/overworld-hidden-item-pointers.json
diff -u data/extracted/overworld-hidden-item-pointers.json /tmp/overworld-hidden-item-pointers.json
```

The parser parity test ensures all 128 pointer records match the pinned source;
it does not mark the hidden-item list data as fully extracted or editable.

## Overworld high/low payload inventories

The source-only inventory is split by source file into
`data/extracted/overworld-payloads-bank0b.json` (164 declarations) and
`data/extracted/overworld-payloads-bank0c.json` (84 declarations). Together
they capture 248 labelled `incbin` declarations under `bin/ow/` from pinned
revision `347c23f9fc019c72d32da537c9cb235f468d021d`. They remain separate
because each version-1 incbin export retains its source filename and revision.

The records do not include payload bytes. The source comments provide a useful
initial offset map, but they contain known gaps and mismatches:

- Bank0B has 164 entries: 161 range/size matches, two mismatches, and one
  declaration (`OverworldMap32_Screen4F_High`) with no source-commented range.
- `OverworldMap32_Screen42_Low` has a declared size of 237 bytes while its
  source-commented inclusive range covers 269 bytes.
- `OverworldMap32_Screen61_Low` has a declared size of 241 bytes while its
  source-commented inclusive range covers 242 bytes.
- Bank0C has 84 entries: 83 range/size matches and one mismatch.
- `OverworldMap32_Screen88_Low` has a declared size of 84 bytes while its
  source-commented inclusive range covers 83 bytes.

These differences are preserved by the inventory's distinct fields for the
source-commented end, computed end, and boolean comparison. They are not
silently corrected, and the maps' high/low payloads are not decoded by this
export. The pinned submodule has no tracked `bin/ow/*.bin` files.

Reproduce the two inventory files with the existing `inspect-incbin` command:

```bash
uv run zelda-suite inspect-incbin reference/AsarUSALTTPDisassembly/Bank0B.asm --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d --output /tmp/overworld-payloads-bank0b.json
uv run zelda-suite inspect-incbin reference/AsarUSALTTPDisassembly/Bank0C.asm --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d --output /tmp/overworld-payloads-bank0c.json
uv run zelda-suite validate-source-export /tmp/overworld-payloads-bank0b.json
uv run zelda-suite validate-source-export /tmp/overworld-payloads-bank0c.json
diff -u data/extracted/overworld-payloads-bank0b.json /tmp/overworld-payloads-bank0b.json
diff -u data/extracted/overworld-payloads-bank0c.json /tmp/overworld-payloads-bank0c.json
```

Both inventories are registered by name as `overworld-payloads-bank0b` and
`overworld-payloads-bank0c`. CI compares the files to parsed pinned-source
metadata and loads them through the named-asset registry. No editable tile or
layer representation is claimed yet.

Validate the source-local High/Low pairing invariant with:

```bash
uv run zelda-suite validate-overworld-payload-pairs \
  data/extracted/overworld-payloads-bank0b.json \
  data/extracted/overworld-payloads-bank0c.json
```

The command confirms exactly one High and one Low declaration for each of the
124 source-local screen tokens (82 from Bank0B, 42 from Bank0C). It remains a
metadata check; it does not verify annotated offsets against the ROM or decode
the payloads.

## Receive-item source tables

Three raw tables from `Pool_AddReceiveItem` in pinned
`Ancilla/ancilla_init.asm` are now committed and registered:

- `item-receipt-target-addresses.json`: 76 two-byte target addresses from
  `$0484E8–$04857F`.
- `item-receipt-values.json`: 76 one-byte values from `$048580–$0485CB`.
- `item-receipt-dungeon-masks.json`: 14 two-byte masks from `$0485CC–$0485E7`.

Each export is a version-1 `zelda-suite-data-table` containing table index,
calculated file offset, source line, exact source expression, literal value
when directly expressible, and pinned revision. These exports remain raw:
the target-address table names WRAM destinations and is not a ROM pointer
table, and values such as `$FF`, `$FB`, and `$EC` are preserved as byte
patterns rather than converted to semantic item meanings.

The wider receive-item data block also has X/Y offsets, graphics indices,
wide-item flags, and properties. Those arrays remain documented discovery
notes, not part of this PR. In particular, `.item_graphics_indices` comments
skip source index `$40` while the data occupies 76 dense bytes. The new files
do not claim to resolve that comment-index discrepancy or define a canonical
item-ID schema.

Regenerate the three tables using `zelda-suite inspect-data-table` with
`Pool_AddReceiveItem` as the parent label and the corresponding label, offset,
directive, and exclusive next label documented in
[the receive-item discovery note](./schemas/item-receipt-metadata.md). The
tables are then validated and compared with the committed JSON. No ROM bytes
or binary slices are committed.
