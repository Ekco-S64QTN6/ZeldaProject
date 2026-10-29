# Dungeon-room data schema: discovery baseline

Status: **Phase 1 discovery; a read-only long-pointer verifier is implemented, but a local-ROM run remains outstanding.** This note records what the pinned disassembly establishes without guessing the meaning of room object bytes. No room payload bytes or playable-room schema are claimed.

## Authoritative pointer table

At the pinned
[`Bank1F.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Bank1F.asm#L3-L16),
the disassembly declares `RoomData_ObjectDataPointers` at file offsets
`$0F8000–$0F83BF`. The table consists of `dl` expressions, each representing
a 24-bit (three-byte) pointer. The inclusive range is `0x3C0` bytes, or 960
bytes, which gives 320 pointer-table entries indexed `0x000–0x13F`.

For a pointer-table index `i`, the pointer-entry file offset is:

```text
pointer_entry_file_offset = 0x0F8000 + (i * 3)
```

This formula locates the pointer entry, not the room-data target. The file
offset follows the canonical headerless LoROM mapping described in
[`rom-offsets.md`](../references/rom-offsets.md).

## Companion door-data pointer table

The same pinned `Bank1F.asm` declares `RoomData_DoorDataPointers` at
`$0F83C0–$0F877F`, immediately after the object-pointer table. This is another
320-entry table of three-byte `dl` expressions, with pointer-entry offsets
calculated as:

```text
pointer_entry_file_offset = 0x0F83C0 + (i * 3)
```

The committed source export is
[`dungeon-room-door-pointers.json`](../../data/extracted/dungeon-room-door-pointers.json),
registered as `dungeon-room-door-pointers`. All 320 entries have numeric
addends and their parsed target labels align slot-for-slot with
`RoomData_ObjectDataPointers`: 263 distinct target labels, including 39
`RoomDataTiles_Empty` entries. The regression test protects that relationship
without needing the source submodule at runtime; the pinned-source parser test
also checks all 320 records when the submodule is present.

Preserve both the complete original pointer expression and parsed addend.
Although the label names correspond across the two tables, the addends have
not been semantically decoded or verified against a local ROM. Do not treat
them as confirmed door-data offsets or use either table to infer a playable-room
count.

A source-only bounds regression joins each target label to the three registered
payload inventories and checks that every numeric addend is within that label's
source-annotated declared size (320/320 entries in the current pinned exports).
This is only arithmetic consistency against source comments: it does not read
payload bytes, establish that the size annotations are correct, decode door
semantics, or verify target offsets against a ROM.

## Count discrepancy to resolve

The roadmap currently refers to 296 dungeon rooms, while this disassembly table
spans 320 indices. Those figures must not be treated as interchangeable. The
table includes references to `RoomDataTiles_Empty` and repeated/shared target
expressions; it does not by itself establish which indices are usable playable
rooms. Preserve raw pointer-table indices in extracted data and determine the
user-facing room set only after corroborating with runtime/tool behavior.

## What the source establishes

- `RoomData_ObjectDataPointers` is located at `$0F8000–$0F83BF` in the
  pinned disassembly and contains three-byte `dl` entries.
- Entries refer to named targets including `RoomDataTiles_0000` and
  `RoomDataTiles_Empty`. The target expression, including any offset suffix,
  must be retained for auditability rather than replaced with an inferred ID.
- [`Bank0A.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Bank0A.asm#L3-L25)
  shows room-data labels mapped to `incbin "bin/rooms/roomXXXX.bin"` files,
  with sizes annotated in comments.
- At pinned disassembly commit
  `347c23f9fc019c72d32da537c9cb235f468d021d`, the tracked tree does not
  contain the referenced `bin/rooms/*.bin` payloads. The labels and some sizes
  are useful evidence, but those binary chunks are not available as ready-made
  fixtures in this repository snapshot.

## Committed source-only pointer inventory

The source declarations are now committed as [`data/extracted/dungeon-room-object-pointers.json`](../../data/extracted/dungeon-room-object-pointers.json) and registered under the name `dungeon-room-object-pointers`. This version-1 `zelda-suite-pointer-table` export contains 320 entries and retains the original index, source expression, parsed target label/addend, source line, and pinned revision. The separate `verify-dungeon-room-pointers` command compares three-byte pointer values against target offsets computed from the first annotated start in each payload inventory plus sequential declared payload sizes. It preserves conflicting raw offset comments as findings in report v2 rather than rewriting them; no playable-room set is inferred.

The export preserves these audit fields:

| Field | Meaning |
| --- | --- |
| `table_index` | Original index, integer `0–319` (hex `0x000–0x13F`) |
| `pointer_entry_file_offset` | Entry location calculated with the formula above |
| `pointer_expression` | Exact source `dl` expression, retained verbatim |
| `target_label` | Parsed assembly target label; not a ROM-resolved address |
| `target_addend` | Parsed signed numeric addend, or `null`; the complete raw expression remains in `pointer_expression` |
| `resolved_target_file_offset` | Nullable until pointer resolution is verified against the ROM |
| `is_empty_target` | Derived only from an explicit `RoomDataTiles_Empty` reference |
| `source_revision` | Pinned disassembly revision used to interpret the table |

This is an audit-oriented discovery record, not a final editable SQLite schema. It keeps the original index and source expression intact even when multiple indices point to shared data. The source table has 320 entries, but the documented 296-room count has not been reconciled. No pointer target has been independently verified against a local ROM.

## Source-label cross-reference

The 320-entry pointer table's distinct target labels can be checked against the
pinned source declarations in `Bank03.asm`, `Bank0A.asm`, and `Bank1F.asm`.
The source-level regression test currently observes:

- 266 unique `RoomDataTiles_*` labels across those three files: 34 in Bank03,
  75 in Bank0A, and 157 in Bank1F.
- 263 distinct target labels in the pointer table, including
  `RoomDataTiles_Empty`; all 263 are defined in those source files.
- Three source labels are defined but not referenced by this table:
  `RoomDataTiles_Orphan`, `RoomDataTiles_Zarby89`, and
  `RoomDataTiles_Zarby90`.
- All 75 labels in the Bank0A payload inventory occur among the pointer
  table's target labels.

This proves only that the symbolic labels exist in the pinned source. The new
pointer verifier maps each candidate start offset to a LoROM CPU address and
compares the corresponding `dl` bytes; until run against a local ROM, candidate
target offsets remain unverified. The word “empty” is retained as a source
label/metadata flag; its runtime/payload semantics still need independent
verification.

## Validation gates before calling extraction complete

1. Add fixtures from a locally supplied clean US ROM or approved local test
   setup. Never commit ROMs or partial ROM slices.
2. Run `zelda-suite verify-dungeon-room-pointers "$ROM"` to compare all 320
   three-byte pointer entries with candidate CPU addresses computed from
   sequential source-order payload layout.
3. Review any pointer mismatches and the separate source-offset findings before
   changing annotations. This check does not verify payload bytes, ROM
   provenance, or the canonical correctness of the first offset in each bank.
4. Establish which indices are actually playable and how empty/shared targets
   behave before exposing a room-editing API. Preserve source indices as-is.

No ROM bytes are read or written by this documentation change.


## Inspect the source table

The source declarations can be parsed (without reading ROM data) with:

```bash
uv run zelda-suite inspect-pointer-table \
  reference/AsarUSALTTPDisassembly/Bank1F.asm \
  RoomData_ObjectDataPointers \
  --table-offset '$0F8000' \
  --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d \
  --output /tmp/room-object-pointers.json
```

See [disassembly source-table inspection](../disassembly-parser.md) for the
output contract and parser limitations. The resulting table should be reviewed
against a local ROM before any source record is treated as a resolved pointer.


## Room payload inventories

The committed source-only room payload inventories cover all 266 labelled
`incbin` declarations associated with room labels in the pinned source:

| Source file | Registry asset | Entries |
| --- | --- | ---: |
| `Bank03.asm` | [`dungeon-room-payloads-bank03`](../../data/extracted/dungeon-room-payloads-bank03.json) | 34 |
| `Bank0A.asm` | [`dungeon-room-payload-inventory`](../../data/extracted/dungeon-room-payload-inventory.json) | 75 |
| `Bank1F.asm` | [`dungeon-room-payloads-bank1f`](../../data/extracted/dungeon-room-payloads-bank1f.json) | 157 |

The files preserve each source label, `bin/rooms/*.bin` path, declared size,
source line, source-commented start, and separately computed end. The source
comments do not give explicit end offsets for these records, so
`source_file_offset_end` and `source_range_size_matches` remain null. The
computed ends are not independently verified ROM offsets. The referenced
binary payload files are absent from the pinned submodule.

The 266 definitions cover all 263 distinct pointer-table target labels, plus
three labels that are not referenced by the table. A regression test unions the
three inventories and asserts exact equality with the source label set, and
checks that all pointer targets are covered. This verifies symbolic coverage in
the source only; it does not resolve `dl` values to ROM addresses, establish the
user-facing playable room set, or close the 296/320 count issue.


## Read-only pointer verification

Run from the repository root after setting `ROM` per
[`real-rom-verification.md`](../real-rom-verification.md):

```bash
uv run zelda-suite verify-dungeon-room-pointers "$ROM" \
  --output /tmp/dungeon-room-pointer-verification.json
```

The command cross-references the 320 source pointer expressions with all three
registered room-payload inventories. It anchors each inventory at its first
source-commented start, advances by the declarations' source-declared payload
sizes, and encodes each resulting candidate as a three-byte LoROM CPU address.
Conflicting comments are preserved in `source_offset_findings`. Its version-2
report schema is [`dungeon-room-pointer-verification.schema.json`](./dungeon-room-pointer-verification.schema.json).
It is strictly read-only and deliberately reports
`provenance_verified: false`, `payload_bytes_verified: false`, and
`playable_room_set_resolved: false`. Run it against a local image and review
mismatches; a successful comparison does not independently prove that the
sequential payload-layout candidates are canonical.


## Cross-reference committed pointer and payload inventories

Run `uv run zelda-suite audit-dungeon-room-assets` to join the registered
`dungeon-room-object-pointers` export with the Bank03, Bank0A, and Bank1F
room-payload inventories. The report checks label uniqueness and source
provenance, shows each pointer slot's matching payload declaration, and lists
unreferenced payload labels or pointer targets without a unique declaration.

The committed metadata baseline contains 320 pointer entries, 39 entries to
`RoomDataTiles_Empty`, 263 distinct pointer target labels, and 266 payload
declarations. All 263 target labels have exactly one matching declaration.
Three declarations—`RoomDataTiles_Orphan`, `RoomDataTiles_Zarby89`, and
`RoomDataTiles_Zarby90`—are not referenced by the pointer table. This is a
source-symbol relationship only. The reported offsets are source-commented
candidate inputs; the command reads neither ROM bytes nor room payload bytes,
and it does not resolve the 296-versus-320 playable-room count discrepancy.
The separate `verify-dungeon-room-pointers` command still requires a local ROM
for pointer-byte comparisons. See the
[dungeon-room asset audit schema](./dungeon-room-asset-audit.schema.json).

## Chest room-to-pointer cross-reference

Pinned \`Bank01.asm\` source supports joining the packed chest room field with the
same room-index domain used by the two room-pointer tables:

- Lines 15108–15109 describe the top-byte item value, low-15-bit room value, and
  bit-15 big-chest flag.
- Line 15231 masks each chest record with \`$7FFF\` and compares that room field
  with the current-room variable \`$A0\`; lines 15236 and 15239 consume the item
  byte and big-chest flag.
- Lines 7908–7911 calculate \`$A0 * 3\` and load the corresponding door-data
  pointer. Lines 826–829 use the same three-byte room index to load object data.

Run \`uv run zelda-suite audit-dungeon-chest-room-references\` to produce a
versioned JSON cross-reference for all 168 chest records and their matching
object/door pointer slots. Against the committed exports, all 168 room values
have matching table slots, there are 106 distinct room values and 32 room
values with multiple chest records, and the object/door pointer target labels
agree for every referenced room slot. Three chest entries reference slots whose
object-pointer target label is \`RoomDataTiles_Empty\`; this preserves the source
label only and does not claim that those rooms are unplayable or invalid.

This verifies a relationship documented by the pinned source consumer, not a
trusted-ROM offset or byte mapping. The room payload binaries are absent from
the pinned tree; item names remain unresolved; and this audit does not settle
the separate 296-versus-320 playable-room discrepancy. See the
[chest room-reference audit schema](./dungeon-chest-room-reference-audit.schema.json).

## Door-pointer addend audit

Run `uv run zelda-suite audit-dungeon-room-door-pointers` to cross-reference
all 320 `RoomData_DoorDataPointers` entries against their matching object-pointer
slots and the three registered room-payload inventories. The report preserves
each raw pointer expression and reports whether its numeric addend fits within
the target payload's source-declared size. Use `--fail-on-findings` in scripts
to make a warning or error fail the command.

The pinned inventories currently report 320/320 addends within the annotated
payload sizes, zero target-label slot differences, and zero missing target
labels. The report also surfaces the same three payload declarations that are
not referenced by the pointer table. These are source-metadata arithmetic
checks only: source-declared sizes may be wrong, payload bytes are absent from
the pinned tree, and no pointer offsets or door semantics are verified against
a ROM. The 320 pointer slots do not establish a playable-room count.
See the [door-pointer audit schema](./dungeon-room-door-pointer-audit.schema.json).

The report contract is also indexed in [the schema catalog](./README.md). Its 320 in-range results apply only to the source-declared sizes in the pinned inventory; they do not independently validate the actual payload size or pointer offsets.

 
## Project-aware chest room-reference audit

Run `uv run zelda-suite audit-project-dungeon-chest-room-references project/my-hack.db`
after importing the chest model and making any local edits. This query uses each
record's current `room_value`, not its original source room value, to select
the corresponding object- and door-pointer slots. It carries the original room
value and `is_modified` state into each report row so edits can be reviewed
against the imported baseline.

This differs from `audit-dungeon-chest-room-references`, which joins only the
committed source inventory. The project-aware report is still source-metadata
evidence: pointer offsets are unverified annotations, payload bytes are not
read, raw item values are not names, and a pointer-table slot is not proof of a
playable room. It does not access or modify ROM bytes. The 296-versus-320
playable-room count discrepancy remains unresolved. Use `--fail-on-findings`
to make out-of-range edited room values or object/door target-label mismatches
return a failing exit code. The report contract is
[`project-dungeon-chest-room-reference-audit.schema.json`](project-dungeon-chest-room-reference-audit.schema.json).
