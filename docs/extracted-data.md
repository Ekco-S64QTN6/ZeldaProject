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

## Crystal Maiden message IDs

`data/extracted/crystal-maiden-message-ids.json` preserves nine raw `dw` expressions under
`CrystalMaiden_ShowMessage_message_ids` in pinned
`Sprites/sprite_crystal_maiden.asm` revision `347c23f9fc019c72d32da537c9cb235f468d021d`. The source comment
marks `$0F4EBC–$0F4ECD`. The values are message IDs rather than decoded message
content.

Each of the eight distinct IDs cross-references to an existing record in the
committed `text-message-index.json` export (from `Message_0132` through
`Message_013C` across the listed values). The nearby
`CrystalMaiden_ShowMessage` routine reads from a local `.message_ids`
reference; this export does not establish that this local name resolves to the
global `CrystalMaiden_ShowMessage_message_ids` label. Keep that source-label
relationship unresolved. Source-commented offsets have not been verified
against a local ROM.

Regenerate the table from the pinned source:

```bash
uv run zelda-suite inspect-data-table \
  reference/AsarUSALTTPDisassembly/Sprites/sprite_crystal_maiden.asm \
  CrystalMaiden_ShowMessage_message_ids \
  --table-offset '$0F4EBC' \
  --directive dw \
  --entry-count 9 \
  --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d \
  --output /tmp/crystal-maiden-message-ids.json
uv run zelda-suite validate-source-export /tmp/crystal-maiden-message-ids.json
diff -u data/extracted/crystal-maiden-message-ids.json /tmp/crystal-maiden-message-ids.json
```

CI checks source-parser parity and that all distinct IDs exist in the registered
message index. It does not decode text or resolve the local `.message_ids`
label to the global table label, and it does not read ROM bytes.

## OAM allocator limits and fallback points

`data/extracted/oam-buffer-position-table.json` preserves all 54 `dw` entries
under `Pool_OAM_GetBufferPosition` from pinned
`Sprites/sprite_oam_allocation.asm` revision
`347c23f9fc019c72d32da537c9cb235f468d021d`. The source comment marks
`$06BA9E–$06BB09` (108 bytes). The first six words belong to `.limits`;
the remaining 48 belong to `.fallback_points`.

`OAM_AllocateFromRegionA` through `OAM_AllocateFromRegionF` select Y values
`$00`, `$02`, `$04`, `$06`, `$08`, or `$0A`. `OAM_GetBufferPosition`
uses the selected limit and, on overflow, indexes eight fallback words per
region using the region selector and a counter slot masked to 0–7.
`zelda-suite audit-oam-allocation` reports six A–F rows with a limit and eight
fallback entries each.

```bash
uv run zelda-suite audit-oam-allocation
uv run zelda-suite audit-oam-allocation --output /tmp/oam-allocation-audit.json
```

The report preserves source expressions and metadata; it does not execute sprite
allocation or prove the source-commented offsets or OAM buffer positions against
a local ROM. The complete editable sprite-placement schema remains future work.
See [the sprites discovery guide](./schemas/sprites.md) and
[audit report schema](./schemas/oam-allocation-audit.schema.json).

## Mixed-width Landmine OAM group rows

`data/extracted/landmine-oam-groups.json` preserves both source rows under
`Landmine_Draw_OAM_groups` from pinned
`Sprites/sprite_landmine.asm` revision
`347c23f9fc019c72d32da537c9cb235f468d021d`. The source comment marks
`$0E80FC–$0E810B`. Each row contains a two-entry `dw` field followed by a
four-entry `db` field, for eight bytes per row and 16 bytes total.

The new `inspect-mixed-data-table` parser records each directive field,
expression, numeric literal where directly present, source line, and calculated
byte offset. It does not evaluate Asar expressions or infer sprite/OAM
semantics. The offset remains source-commented metadata, not a verified ROM
address.

Regenerate and validate the source-only export:

```bash
uv run zelda-suite inspect-mixed-data-table \
  reference/AsarUSALTTPDisassembly/Sprites/sprite_landmine.asm \
  Landmine_Draw_OAM_groups \
  --table-offset '$0E80FC' \
  --record-count 2 \
  --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d \
  --output /tmp/landmine-oam-groups.json
uv run zelda-suite validate-source-export /tmp/landmine-oam-groups.json
diff -u data/extracted/landmine-oam-groups.json /tmp/landmine-oam-groups.json
```

CI covers both the generic mixed-width parser and the committed export's parity
with the pinned source. No ROM bytes, decoded sprite geometry, or editable OAM
model are claimed.

## Crystal Maiden palette words

`data/extracted/crystal-maiden-palette-words.json` records the eight raw
`dw` literals under `CrystalMaiden_Configure_palette` in pinned
`Sprites/sprite_crystal_maiden.asm` revision
`347c23f9fc019c72d32da537c9cb235f468d021d`. The source comment marks the
16-byte range `$0F4CD3–$0F4CE2`; the values are preserved as 16-bit words
without converting them into rendered RGB colors.

There is a source-symbol caveat: the nearby `CrystalMaiden_Configure` routine
loads eight words from `.palette+$00` through `.palette+$0E` into
`$7EC5E0–$7EC5EE`, but the standalone data label in the source is
`CrystalMaiden_Configure_palette`. This export records the declared data and
the adjacent code pattern without asserting that the two spellings resolve to
the same symbol. That relationship and the source-commented file offset remain
unverified against the assembler/build and a local ROM.

Regenerate the source table with:

```bash
uv run zelda-suite inspect-data-table \
  reference/AsarUSALTTPDisassembly/Sprites/sprite_crystal_maiden.asm \
  CrystalMaiden_Configure_palette \
  --table-offset '$0F4CD3' \
  --directive dw \
  --entry-count 8 \
  --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d \
  --output /tmp/crystal-maiden-palette-words.json
uv run zelda-suite validate-source-export /tmp/crystal-maiden-palette-words.json
diff -u data/extracted/crystal-maiden-palette-words.json /tmp/crystal-maiden-palette-words.json
```

CI compares the committed words against the pinned source parser. It does not
resolve the routine's `.palette` symbol, decode colors, or validate ROM bytes.

## Crystal Switch palette selector

`data/extracted/crystal-switch-palette-selectors.json` preserves the two
`db` values under `Sprite_CrystalSwitch_palettes` in the pinned
`Sprites/sprite_crystal_switch.asm` revision
`347c23f9fc019c72d32da537c9cb235f468d021d`. The source comment marks the
range `$0338CE–$0338CF`.

The source consumer in `Sprites/sprite_prep.asm` reads bit zero of
`$7EC172`, uses that bit as the two-entry table index, and ORs the selected
byte into the sprite properties at `$0F50,X`. The values `$02` and `$04`
are palette-field selector bits, not RGB colors or a decoded palette. The
source-commented offsets have not been independently verified against a local
ROM.

Regenerate the export from the pinned source:

```bash
uv run zelda-suite inspect-data-table \
  reference/AsarUSALTTPDisassembly/Sprites/sprite_crystal_switch.asm \
  Sprite_CrystalSwitch_palettes \
  --table-offset '$0338CE' \
  --directive db \
  --entry-count 2 \
  --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d \
  --output /tmp/crystal-switch-palette-selectors.json
uv run zelda-suite validate-source-export /tmp/crystal-switch-palette-selectors.json
diff -u data/extracted/crystal-switch-palette-selectors.json /tmp/crystal-switch-palette-selectors.json
```

CI checks the exact table expressions and the source consumer. This is pinned
source-parity evidence, not a local-ROM byte check or a complete sprite/color
palette extraction.

## Mad Batter pseudo-attack palette selector

`data/extracted/mad-batter-pseudo-attack-palettes.json` preserves the eight
`db` bytes under `MadBatter_PseudoAttackPlayer_palettes` in the pinned
`Sprites/sprite_mad_batter.asm` revision
`347c23f9fc019c72d32da537c9cb235f468d021d`. The source comment marks the
range `$02FB86–$02FB8D`.

The `MadBatter_PseudoAttackPlayer` routine forms a three-bit table index
(`LSR`, then `AND #$07`) and combines the selected byte with the sprite
properties at `$0F50,X`. This export records those selector bytes only; it
does **not** contain decoded RGB/color-palette entries. The source-annotated
offset has not been independently verified against a local ROM.

Regenerate the source table with the pinned revision:

```bash
uv run zelda-suite inspect-data-table \
  reference/AsarUSALTTPDisassembly/Sprites/sprite_mad_batter.asm \
  MadBatter_PseudoAttackPlayer_palettes \
  --table-offset '$02FB86' \
  --directive db \
  --entry-count 8 \
  --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d \
  --output /tmp/mad-batter-pseudo-attack-palettes.json
uv run zelda-suite validate-source-export /tmp/mad-batter-pseudo-attack-palettes.json
diff -u data/extracted/mad-batter-pseudo-attack-palettes.json /tmp/mad-batter-pseudo-attack-palettes.json
```

CI compares the committed records against the pinned source parser and checks
the eight literal values and sequential offsets. This is source-parity evidence,
not a local-ROM check or a complete sprite/color-palette extraction.

## SpritePrep_Main inline dispatch table

`data/extracted/sprite-prep-dispatch.json` preserves the 243 `dw` entries
after `UseImplicitRegIndexedLocalJumpTable` in `SpritePrep_Main` from pinned
`Sprites/sprite_prep.asm` revision `347c23f9fc019c72d32da537c9cb235f468d021d`.
The source-commented routine region is `$03064D-$030840 JUMP LOCATION`, but it
does not establish the exact start offset of this inline table. The export
therefore records `table_file_offset: null` and
`table_offset_established: false`, rather than deriving an offset from the
routine's total range.

Each entry preserves its source line, ID comment, raw handler expression,
optional symbol label, address annotation, description and wrapped continuation
comments. The literal `$0000` entry is retained as a literal with no handler
label. These handler address annotations are source comments, not confirmed
ROM pointers.

Inspect/regenerate from the pinned source:

```bash
uv run zelda-suite inspect-sprite-prep-dispatch \
  reference/AsarUSALTTPDisassembly/Sprites/sprite_prep.asm \
  --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d \
  --entry-count 243 \
  --output /tmp/sprite-prep-dispatch.json
uv run zelda-suite validate-source-export /tmp/sprite-prep-dispatch.json
diff -u data/extracted/sprite-prep-dispatch.json /tmp/sprite-prep-dispatch.json
uv run zelda-suite audit-sprite-prep-dispatch
```

The audit cross-references the 243 preparation IDs with the 68
`SpriteActive3_Table` IDs (`$79–$BC`): all 68 lie in the prep-table ID range.
The report joins rows by ID only. Prep dispatch and active-loop dispatch are
different stages; the report does not claim their handlers are semantically
equivalent, and it does not read ROM bytes or verify either source-commented
handler address.

See the [sprite discovery guide](./schemas/sprites.md) and the
[source-export schema](./schemas/sprite-prep-dispatch-export.schema.json) and
[audit schema](./schemas/sprite-prep-dispatch-audit.schema.json).

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
file offsets, decode hidden-item lists, or interpret the one-byte value
semantics. Pinned-source accounting for `$0DC3F9–$0DC89B` finds 351 three-byte
`dw $xxxx : db $yy` entries and 67 two-byte `dw $FFFF` words, totaling the
full `0x4A3`-byte range. The `Overworld_RevealSecret` source reader scans in
three-byte strides until a leading `$FFFF` word; it does not stop at source
label boundaries. This is source-level evidence only: the pointer targets,
record bytes, and per-area grouping still need comparison with a trusted local
US ROM before the list data is considered extracted or editable.

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

A separate submodule-independent CI regression test pins all 128 committed
pointer slots, their sequential two-byte offsets, all 80 distinct target labels,
and the repeated-label distribution (64 labels used once and 16 used four times).
This catches drift in the committed export even when the source parser parity
test is skipped because the reference submodule is absent. It does not resolve
any target to a binary file offset or verify ROM bytes.

For a source-only view of the full mixed-width declaration region, run:

```bash
uv run zelda-suite inspect-overworld-hidden-items \
  --output /tmp/overworld-hidden-item-source-layout.json
```

This report adds computed label offsets, raw three-byte records, two-byte
sentinels, source-derived area listings, and replacement words. It reads no ROM
and is not a registered asset; `rom_verified` and `semantic_values_decoded` are
explicitly false. See the [report schema](./schemas/overworld-hidden-item-source-layout.schema.json).

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

Eight raw tables from `Pool_AddReceiveItem` in pinned
`Ancilla/ancilla_init.asm` are committed and registered:

| Asset | Source label | Offset range | Width / count |
| --- | --- | --- | --- |
| `item-receipt-y-offsets` | `.y_offsets` | `$04836C–$0483B7` | 1 byte × 76 |
| `item-receipt-x-offsets` | `.x_offsets` | `$0483B8–$048403` | 1 byte × 76 |
| `item-receipt-graphics-indices` | `.item_graphics_indices` | `$048404–$04844F` | 1 byte × 76 (v2 comments) |
| `item-receipt-wide-flags` | `.wide_item_flag` | `$048450–$04849B` | 1 byte × 76 |
| `item-receipt-properties` | `.properties` | `$04849C–$0484E7` | 1 byte × 76 |
| `item-receipt-target-addresses` | `.item_target_addr` | `$0484E8–$04857F` | 2 bytes × 76 |
| `item-receipt-values` | `.item_values` | `$048580–$0485CB` | 1 byte × 76 |
| `item-receipt-dungeon-masks` | `.item_masks` | `$0485CC–$0485E7` | 2 bytes × 14 |

The seven version-1 `zelda-suite-data-table` exports record table index,
calculated file offset, source line, exact expression, literal value when
directly expressible, and pinned revision. The graphics-index table uses
version 2 to preserve its inline comment on each entry. These are raw positional arrays, not a
complete semantic item catalog. The target-address table contains WRAM
destinations, not ROM pointers. Byte patterns such as `$FF`, `$FB`, and
`$EC` remain raw values; runtime signed-byte behavior has not been normalized
into editorial item meanings. Signed decimal offset/property expressions such
as `-5` or `-1` stay as expressions with a null literal value.

The parallel arrays `.y_offsets`, `.x_offsets`, `.wide_item_flag`, and
`.properties` share the same 76-position table index as the two 76-entry
target/value arrays. The 14-word `.item_masks` array is separate. The
The separate `item-receipt-graphics-indices` export preserves all 76 dense bytes
and the inline comments that enumerate `0x00–0x3F`, then `0x41–0x4C`.
Its dense `table_index` is deliberately not rewritten to match those comment
IDs; the missing `0x40` comment remains unresolved and is not normalized into
a canonical item-ID schema.

Regenerate each table using `zelda-suite inspect-data-table` with
`Pool_AddReceiveItem` as the parent label, the table's offset/directive, and
its exclusive next label from
[the receive-item discovery note](./schemas/item-receipt-metadata.md). Omit
`--end-label` for `.item_masks`. Validate and diff the resulting JSON before
reviewing a data update. No ROM bytes or binary slices are committed.

The joined `item-receipt-layout` export aligns the six 76-entry arrays by
`table_index` while retaining every field's source label, offset, raw
expression, and numeric literal when parsed. It preserves the 14 dungeon masks
separately and carries `semantic_item_ids_resolved: false`; the source-comment
gap around index `$40` is still unresolved. Regenerate and compare it with:

```bash
uv run zelda-suite join-item-receipt-tables \
  --output /tmp/item-receipt-layout.json
uv run zelda-suite validate-source-export /tmp/item-receipt-layout.json
diff -u data/extracted/item-receipt-layout.json /tmp/item-receipt-layout.json
```

The joined view is registered as a 76-record asset. It is a convenience layout,
not a canonical item catalog or a ROM-derived payload.


## Standard shopkeeper purchase handlers

The registered [`shop-item-handlers`](../data/extracted/shop-item-handlers.json)
export preserves the seven purchase handlers selected by variant IDs 7–13 in
`Sprite_ShopKeeper` from pinned `Sprites/sprite_shopkeeper.asm` revision
`347c23f9fc019c72d32da537c9cb235f468d021d`. The containing routine range is
annotated as `$0F6EEF-$0F6F11 JUMP LOCATION`, but the source does not establish
an exact byte offset for the inline dispatch table. It remains null in the
export. Source handler addresses and their routine-range comments are retained
as annotations, not verified ROM pointers.

Each purchase handler has an `LDA.b #$low`, `LDY.b #$high` pair passed to
`ShopKeeper_TryToGetPaid`; the exporter records the two literal byte
expressions and their combined 16-bit value. It also captures the Y selector
passed to `ShopItem_HandleReceipt`. The audit joins those seven selector
values to the same-numbered indexes in the existing 76-slot
`item-receipt-layout` export, preserving raw receipt-field expressions and
offsets. These are positional indexes, not canonical semantic item IDs.

Inspect and cross-reference:

```bash
uv run zelda-suite inspect-shop-item-handlers reference/AsarUSALTTPDisassembly/Sprites/sprite_shopkeeper.asm --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d --entry-count 7 --output /tmp/shop-item-handlers.json
uv run zelda-suite validate-source-export /tmp/shop-item-handlers.json
diff -u data/extracted/shop-item-handlers.json /tmp/shop-item-handlers.json
uv run zelda-suite audit-shop-item-handlers
```

The source-derived price values are 150, 50, 500, 10, 30, 50, and 10; the
receipt selector indexes are 46, 4, 5, 66, 68, 49, and 14. This audit does not
read ROM bytes, verify price behavior at runtime, resolve receipt slots to item
names, or establish which handlers are stocked in particular rooms. See
[`items.md`](./schemas/items.md), the
[export schema](./schemas/shop-item-handlers-export.schema.json), and the
[audit schema](./schemas/shop-item-handlers-audit.schema.json).

## Potion-shop transactions

The registered [`potion-shop-transactions`](../data/extracted/potion-shop-transactions.json)
export contains the green, blue, and red potion handlers from pinned
`Sprites/sprite_potion_shop.asm` revision
`347c23f9fc019c72d32da537c9cb235f468d021d`. Their source rupee-balance
comparison and deduction literals are `$003C` (60), `$00A0` (160), and
`$0078` (120). All three blocks call `Sprite_GetEmptyBottleIndex` and pass
receipt selectors `$2F`, `$30`, and `$2E` to `Link_ReceiveItem`.

Inspect and audit these source transactions:

```bash
uv run zelda-suite inspect-potion-shop-transactions reference/AsarUSALTTPDisassembly/Sprites/sprite_potion_shop.asm --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d --entry-count 3 --output /tmp/potion-shop-transactions.json
uv run zelda-suite validate-source-export /tmp/potion-shop-transactions.json
diff -u data/extracted/potion-shop-transactions.json /tmp/potion-shop-transactions.json
uv run zelda-suite audit-potion-shop-transactions
```

The audit joins each selector to its raw receive-item slot and the graphics-index
comment at that dense table position. This preserves the source labels
`POTION REFILL (GREEN)`, `POTION REFILL (BLUE)`, and `POTION REFILL (RED)`
as annotations only. It does not establish canonical semantic item IDs, verify
price behavior at runtime, verify source range annotations against a ROM, or
describe room-specific potion stock. See the [item/chest guide](./schemas/items.md)
and the [transaction audit schema](./schemas/potion-shop-transactions-audit.schema.json).

## Bomb Shop and Bottle Vendor transactions

The registered [`special-shop-transactions`](../data/extracted/special-shop-transactions.json) export records two Bomb Shop purchases and the Bottle Vendor's bottle sale from pinned `Sprites/sprite_bomb_shop_entity.asm` and `Sprites/sprite_bottle_vendor.asm` revision `347c23f9fc019c72d32da537c9cb235f468d021d`.

All three paths encode a 100-rupee price. The Bomb Shop Bomb passes A/Y literals `$64/$00` to `ShopKeeper_TryToGetPaid` and calls `ShopItem_HandleReceipt` with selector `$28`. The Super Bomb uses the same payment literals but writes `$0D` to `$7EF3CC` and spawns a tagalong; it does not call the receipt handler, so its receipt selector stays null. The Bottle Vendor compares the rupee balance to `$0064`, later deducts `$0064`, and passes selector `$16` to `Link_ReceiveItem`; the associated source comment is preserved as an annotation, not a canonical item identity.

Reproduce and audit the export:

```bash
uv run zelda-suite inspect-special-shop-transactions reference/AsarUSALTTPDisassembly/Sprites/sprite_bomb_shop_entity.asm reference/AsarUSALTTPDisassembly/Sprites/sprite_bottle_vendor.asm --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d --entry-count 3 --output /tmp/special-shop-transactions.json
uv run zelda-suite validate-source-export /tmp/special-shop-transactions.json
diff -u data/extracted/special-shop-transactions.json /tmp/special-shop-transactions.json
uv run zelda-suite audit-special-shop-transactions
```

The audit joins only receipt selectors `$28` and `$16` to dense positions in the 76-entry receive-item layout and retains the graphics-table comment annotations at those positions. It does not infer room-specific shop stock, resolve semantic item IDs, verify prices/rewards against runtime, or prove that source range comments are ROM offsets. See the [item/chest guide](./schemas/items.md) and the [export](./schemas/special-shop-transactions-export.schema.json) and [audit](./schemas/special-shop-transactions-audit.schema.json) schemas.

## Paid overworld interaction catalog

The registered [`paid-overworld-interactions`](../data/extracted/paid-overworld-interactions.json)
export captures seven fee-bearing interactions from six files in pinned
`AsarUSALTTPDisassembly` revision `347c23f9fc019c72d32da537c9cb235f468d021d`:

- Fortune Teller readings: `FortuneTeller_Prices` selects 10, 15, 20, or 30 rupees and is consumed by both Light World and Dark World paths.
- Digging Game entry: source compare and deduction use `$0050` (80 rupees), followed by minigame initialization.
- Zora King Flippers sale: `$01F4` (500 rupees) is deducted before the Flippers spawn path.
- Kiki: 10 rupees for the follow transaction and 100 rupees for the follow-up progression transaction.
- Archery Game: the game-entry branch deducts `$0014` (20 rupees).
- Lake Hylia Fairy: `FairyPond.prices` selects 5, 20, 25, or 50 rupees; the accepted amount is deducted and added to the happiness-pond total.

The Digging Game reward structures remain separate: the eight-entry
`DiggingGameGuy_AttemptPrizeSpawn` dispatch table, four raw basic reward bytes
(`$DB/$DA/$D9/$DF`) with source comments, and the heart-piece gate at 25 holes
with flag `$7FFE00`, random mask `#$03`, and write of `$EB` to that flag.
This preserves source logic without claiming a runtime probability or canonical
item catalog.

Regenerate and audit the inventory:

```bash
uv run zelda-suite inspect-paid-overworld-interactions \
  reference/AsarUSALTTPDisassembly/Sprites/sprite_archery_game_guy.asm \
  reference/AsarUSALTTPDisassembly/Sprites/sprite_digging_game_guy.asm \
  reference/AsarUSALTTPDisassembly/Sprites/sprite_fortune_teller.asm \
  reference/AsarUSALTTPDisassembly/Sprites/sprite_kiki.asm \
  reference/AsarUSALTTPDisassembly/Sprites/sprite_ponds.asm \
  reference/AsarUSALTTPDisassembly/Sprites/sprite_zora_king.asm \
  --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d \
  --output /tmp/paid-overworld-interactions.json
uv run zelda-suite validate-source-export /tmp/paid-overworld-interactions.json
diff -u data/extracted/paid-overworld-interactions.json /tmp/paid-overworld-interactions.json
uv run zelda-suite audit-paid-overworld-interactions
```

The catalog and audit are source-only; source annotations, fee behavior, and
reward probabilities have not been verified against ROM execution.


## Receive-item graphics comment annotations

The source-only `audit-item-receipt-annotations` report compares the dense
76-slot `.item_graphics_indices` table in pinned `Ancilla/ancilla_init.asm`
against the IDs written in each inline comment. It finds 64 comments whose IDs
match their table positions and 12 mismatches: table positions `$40–$4B` carry
comments `$41–$4C`, because comment ID `$40` is missing. The report keeps the
raw comment text and calculated delta; it does not treat labels as canonical
item IDs or repair the source.

The shop purchase-handler audit includes the same raw annotations on each
receipt-slot cross-reference. Selectors `$42` and `$44` join by dense table
position and therefore retain comments `0x43 - HEART` and `0x45 - 10 ARROWS`
as source annotations with a +1 delta. These mismatches are explicitly
reported rather than hidden behind inferred semantic names.

Run the annotation audit with:

```bash
uv run zelda-suite audit-item-receipt-annotations
uv run zelda-suite audit-item-receipt-annotations --output /tmp/item-receipt-annotation-audit.json
```

See the [item/chest discovery guide](./schemas/items.md) and the
[annotation audit schema](./schemas/item-receipt-annotation-audit.schema.json).

## Packed dungeon chest records

The registered [`dungeon-chest-data`](../data/extracted/dungeon-chest-data.json)
export preserves all 168 `dl` records under `Dungeon_ChestData` from pinned
`Bank01.asm` revision `347c23f9fc019c72d32da537c9cb235f468d021d`. The source
comments annotate `$00E96E-$00EB65`, a 504-byte span. The export records
candidate per-entry offsets from that range but does not verify them against a
local ROM.

The source comments define the packed value: the top byte is the item value,
the low 15 bits are the room value, and bit 15 (`0x8000`) marks a big chest.
The source consumer iterates three-byte entries, matches the room field, reads
the top-byte item value, and tests the big-chest flag. The JSON keeps item and
room values raw; it does not resolve item names or claim verified room IDs.

Run the source parser and audit:

```bash
uv run zelda-suite inspect-dungeon-chest-data reference/AsarUSALTTPDisassembly/Bank01.asm --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d --entry-count 168 --output /tmp/dungeon-chest-data.json
uv run zelda-suite validate-source-export /tmp/dungeon-chest-data.json
diff -u data/extracted/dungeon-chest-data.json /tmp/dungeon-chest-data.json
uv run zelda-suite audit-dungeon-chest-data
```

The source-only audit counts 106 distinct room values, 32 room values with
multiple entries, 11 entries with the big-chest bit set, 157 without it, and 33
distinct raw item values. Repeated room values are retained because the source
consumer iterates among multiple chest records for one room. See the
[item/chest discovery guide](./schemas/items.md), the
[export schema](./schemas/dungeon-chest-data-export.schema.json), and the
[audit schema](./schemas/dungeon-chest-data-audit.schema.json).

## Dungeon room object-pointer table

`data/extracted/dungeon-room-object-pointers.json` records the 320
`dl` expressions under `RoomData_ObjectDataPointers` in pinned
`Bank1F.asm` at revision `347c23f9fc019c72d32da537c9cb235f468d021d`.

- Headerless source-commented range: `$0F8000–$0F83BF` (960 bytes).
- Entry width/count: three bytes × 320 entries; indices `0x000–0x13F`.
- First pointer-entry location: `$0F8000`; last pointer-entry location: `$0F83BD`.
- The inventory preserves every source expression, parsed target label/addend,
  source line, and pinned revision. Explicit `RoomDataTiles_Empty` targets are
  marked as empty entries. The read-only `verify-dungeon-room-pointers` command can compare all 320 pointer words with candidate addresses calculated from the three registered room-payload inventories.
- The asset is registered as `dungeon-room-object-pointers`. The 320 entries
  are not assumed to be 320 playable rooms; the roadmap's 296-room figure and
  this table's extent remain an unresolved count discrepancy. The verifier uses source-commented payload offsets only as candidates; local byte agreement does not validate the payload bytes or prove canonical offset provenance.

Regenerate and compare the source-only export with:

```bash
uv run zelda-suite inspect-pointer-table \
  reference/AsarUSALTTPDisassembly/Bank1F.asm \
  RoomData_ObjectDataPointers \
  --table-offset '$0F8000' \
  --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d \
  --output /tmp/dungeon-room-object-pointers.json
uv run zelda-suite validate-source-export /tmp/dungeon-room-object-pointers.json
diff -u data/extracted/dungeon-room-object-pointers.json /tmp/dungeon-room-object-pointers.json
```

The parser-parity test verifies the export against the pinned assembly source.
It does not resolve the three-byte target expressions against a local ROM or
establish the playable-room set. The referenced `bin/rooms/*.bin` payloads
are absent from the pinned submodule tree; no ROM bytes are committed.


## Dungeon room door-data pointer table

`data/extracted/dungeon-room-door-pointers.json` records all 320
`dl` expressions under `RoomData_DoorDataPointers` in the pinned
`Bank1F.asm` revision `347c23f9fc019c72d32da537c9cb235f468d021d`.

- Source-commented range: `$0F83C0–$0F877F` (960 bytes).
- Entry width/count: three bytes × 320 entries; indices `0x000–0x13F`.
- First pointer expression: `RoomDataTiles_0000+$004D`; final expression:
  `RoomDataTiles_Empty+$0008`.
- The export retains every raw expression, parsed target label and numeric
  addend, source line, and pinned revision. All 320 target labels agree with
  the corresponding `RoomData_ObjectDataPointers` slot; 263 distinct labels
  are present, including 39 references to `RoomDataTiles_Empty`.
- This is source metadata only. The addends are not promoted to verified door
  offsets or decoded semantics; the referenced payload binaries are absent and
  no local-ROM byte comparison has been performed.

Regenerate and compare the source-only export with:

```bash
uv run zelda-suite inspect-pointer-table \
  reference/AsarUSALTTPDisassembly/Bank1F.asm \
  RoomData_DoorDataPointers \
  --table-offset '$0F83C0' \
  --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d \
  --output /tmp/dungeon-room-door-pointers.json
uv run zelda-suite validate-source-export /tmp/dungeon-room-door-pointers.json
diff -u data/extracted/dungeon-room-door-pointers.json /tmp/dungeon-room-door-pointers.json
```

The parser-parity test checks the complete export against the pinned assembly
source when the submodule is available. A separate regression checks slot-wise
target-label alignment with the committed object-pointer table independently
of the submodule. A separate source-only bounds regression confirms
that each of the 320 addends is smaller than the target label's declared
payload size in the current inventory. These sizes are source annotations, not
verified payload lengths; this check does not establish ROM offsets or door
semantics.

## Dungeon room payload declarations

Three source-only inventories cover all labelled room payload `incbin`
declarations in the pinned source banks that define `RoomDataTiles_*` labels:

| Asset | Source file | Declarations |
| --- | --- | ---: |
| `dungeon-room-payloads-bank03` | `Bank03.asm` | 34 |
| `dungeon-room-payload-inventory` | `Bank0A.asm` | 75 |
| `dungeon-room-payloads-bank1f` | `Bank1F.asm` | 157 |
| **Total** | **three pinned banks** | **266** |

Each export links a source label to its `bin/rooms/*.bin` include path and
retains the source line, declared `Size:`, source-commented start offset, and
a separate computed end offset. All 266 declarations have start-offset
comments and size annotations but no explicit source-commented end offset.
Therefore `source_file_offset_end` and `source_range_size_matches` remain
null, while `computed_file_offset_end` is only arithmetic from the annotated
start plus the declared size. It must not be treated as independently verified
against a ROM. The referenced room binaries are absent from the pinned
submodule tree.

Across these three files, all 263 distinct labels referenced by
`RoomData_ObjectDataPointers` are defined in the source. Three additional
labels (`RoomDataTiles_Orphan`, `RoomDataTiles_Zarby89`, and
`RoomDataTiles_Zarby90`) are defined but not referenced by that pointer
table. This confirms symbol coverage, not resolved ROM addresses or the set of
playable rooms; the 296-versus-320 count discrepancy remains open.

Regenerate, validate, and diff each export with `zelda-suite inspect-incbin`.
For example:

```bash
uv run zelda-suite inspect-incbin \
  reference/AsarUSALTTPDisassembly/Bank03.asm \
  --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d \
  --output /tmp/dungeon-room-payloads-bank03.json
uv run zelda-suite validate-source-export /tmp/dungeon-room-payloads-bank03.json
diff -u data/extracted/dungeon-room-payloads-bank03.json /tmp/dungeon-room-payloads-bank03.json
```

Use the same command with `Bank0A.asm` and `Bank1F.asm` and the corresponding
export filename for the other two inventories. CI compares all three committed
inventories with `parse_incbin_inventory()` over the pinned source and loads
them through the named registry. It does not open the referenced binary payload
files or verify offsets against a local ROM.


### Dungeon pointer/payload source-label coverage

The 320-entry `dungeon-room-object-pointers` inventory has 263 distinct
target labels, including the explicit `RoomDataTiles_Empty` label. The pinned
source defines all 263 labels across `Bank03.asm`, `Bank0A.asm`, and
`Bank1F.asm` (34, 75, and 157 unique `RoomDataTiles_*` definitions
respectively). Three defined labels are not referenced by the pointer table:
`RoomDataTiles_Orphan`, `RoomDataTiles_Zarby89`, and
`RoomDataTiles_Zarby90`. Every label from the Bank0A room payload inventory
is referenced by the pointer table.

This cross-reference is tested from the pinned source tree. It verifies symbol
coverage only; it does not resolve pointer values to ROM offsets or prove
playable-room semantics.


## Cross-inventory incbin audit

Run `uv run zelda-suite audit-incbin-inventory --output /tmp/incbin-audit.json` to summarize the registered music, overworld, and dungeon-room `incbin` inventories in one deterministic report. It lists missing source starts/sizes, explicit range/size discrepancies, and intersections between candidate spans calculated from source annotations. These findings are diagnostic: the command does not correct comments, verify ROM offsets, open payload files, or read ROM bytes. See [`docs/incbin-inventory.md`](./incbin-inventory.md) and the [audit report schema](./schemas/incbin-inventory-audit.schema.json).


## Audit unresolved scalar-table expressions

`uv run zelda-suite audit-unresolved-table-expressions --output /tmp/source-expression-audit.json` summarizes registered scalar-table entries whose values are not represented as numeric literals. It retains their raw expressions and source locations, and classifies syntax shapes without attempting symbol resolution or assembler evaluation. This is useful for tracking extraction coverage before local-ROM verification is available; it is not a ROM-byte verification result. See [the raw data-table parser guide](./data-table-parser.md) and [report schema](./schemas/source-expression-audit.schema.json).


## Cross-check text dictionary exports

Use `uv run zelda-suite audit-text-dictionary --output /tmp/text-dictionary-audit.json`
to cross-check the 98 registered symbolic dictionary pointer entries against
the 98 pointer-to-fragment metadata records. The command validates source
revision and table metadata, pointer/fragment label pairs, entry offsets and
indexes, adjacent fragment start/next-offset relationships, fragment extent
arithmetic, and the terminal sentinel. It reports the existing `.You` extent
discrepancy as a warning: source extent 2 bytes versus 6 bytes from its
directive. The loader's range checks validate consistency within the metadata;
they do not verify source offsets against ROM bytes. The audit does not edit
that source annotation, resolve symbolic pointer values, inspect fragment
payload bytes, or read a ROM. See
[`docs/schemas/text.md`](./schemas/text.md) and the
[text dictionary audit schema](./schemas/text-dictionary-audit.schema.json).


## Audit source message-index diagnostics

Use `uv run zelda-suite audit-text-message-index --output /tmp/message-index-audit.json`
to enumerate known offset-annotation and declared block-size discrepancies in
the registered 397-message index. The current source export records six
annotation mismatches, including three malformed annotations, no per-message
offset annotations for 38 messages in the extra block, and an extra block-size
difference of one byte. This audit reads validated JSON metadata only; it does
not read ROM bytes, decode encoded text, or verify that source offsets match a
trusted ROM. See [the text schema notes](./schemas/text.md) and the
[text-message index audit schema](./schemas/text-message-index-audit.schema.json).


## Audit music pointer/payload cross-references

Use `uv run zelda-suite audit-music-assets --output /tmp/music-audit.json`
to cross-check the 35-entry symbolic music pointer table against the 15
registered payload declarations. It reports the unmatched `Song0B_FairyTheme`
target and the three declarations missing explicit size annotations, while
retaining empty slots and four alias entries. This is a source metadata
diagnostic, not evidence that audio bytes are present or missing in a ROM; the
pinned reference does not track the included `bin/music/` payload files. See
[`docs/schemas/audio.md`](./schemas/audio.md) and the
[music audit schema](./schemas/music-asset-audit.schema.json).


## Cross-check dungeon room pointer and payload assets

Run `uv run zelda-suite audit-dungeon-room-assets --output /tmp/dungeon-room-asset-audit.json`
to join the committed 320-entry long-pointer export with the three registered
room payload inventories (34 Bank03, 75 Bank0A, and 157 Bank1F declarations).
The current source-only baseline finds 263 distinct pointer target labels and
266 unique payload labels: no pointer targets are missing, and exactly three
payload labels are unreferenced (`RoomDataTiles_Orphan`,
`RoomDataTiles_Zarby89`, and `RoomDataTiles_Zarby90`). The command reads
committed JSON only and works without the disassembly submodule. It does not
read ROM or payload bytes, turn source-commented starts into verified
addresses, or determine the playable-room set. See
[`docs/schemas/dungeons.md`](./schemas/dungeons.md) and the
[dungeon-room asset audit schema](./schemas/dungeon-room-asset-audit.schema.json).


## Verify text dictionary pointer words against a local image

Run `uv run zelda-suite verify-text-dictionary-pointers PATH_TO_ROM` to
compare the 98 pointer words at file offset `$074703` against candidate
16-bit values calculated from the registered fragment offsets. The tool
requires an expected-size 1 MiB headerless image and never writes it. It
reports the known `.You` source-extent discrepancy separately from pointer
mismatches. Candidate offsets and ROM provenance remain unverified; the
fragment payload bytes and text decoder are outside this check, and the
`Text_DictionaryPointers`/ `DictionaryPointers` source symbol-name caveat
remains unresolved. See
[`docs/schemas/text.md`](./schemas/text.md) and the
[text dictionary pointer verification schema](./schemas/text-dictionary-pointer-verification.schema.json).


## Compare encoded text-message bytes against a local image

`uv run zelda-suite verify-text-message-bytes PATH_TO_ROM` compares each
literal `db $XX` message byte in source blocks supplied with `--block`
options against the corresponding sequential file offset in a headerless 1 MiB
image. The report includes 397 messages when run with both pinned
`Message_Data` blocks, reports offset-comment and block-size warnings
separately, and never decodes the byte stream into text or semantics. The
parser rejects non-literal expressions and does not execute Asar expressions.
Source offsets and ROM provenance remain unverified; the real-ROM run is a
separate evidence gate. See [text schemas and verification](./schemas/text.md)
and the [text-message byte report schema](./schemas/text-message-byte-verification.schema.json).
