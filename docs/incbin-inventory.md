# Asar `incbin` inventory helper

The Python helper `parse_incbin_inventory()` builds a source-only inventory of
labelled Asar `incbin` declarations. It is intended to help plan extraction
work across room, overworld, music, and graphics assets before binary decoding
is implemented.

## Example

```python
from pathlib import Path

from zelda_suite.extract.incbin_inventory import parse_incbin_inventory

source_path = Path("reference/AsarUSALTTPDisassembly/Bank0B.asm")
records = parse_incbin_inventory(
    source_path.read_text(encoding="utf-8"),
    source_file=str(source_path),
    source_revision="347c23f9fc019c72d32da537c9cb235f468d021d",
)
for record in records:
    print(record.to_dict())
```

Each record retains the source label, include path, source line, declared size
if annotated, file-offset start/end explicitly present in comments, and a
separate computed end when the start and size permit it. When a stated range
and size disagree, `source_range_size_matches` is false; the parser does not
correct the comments. Missing source facts remain null.

## CLI usage

The same inventory is available as stable JSON through:

```bash
uv run zelda-suite inspect-incbin \
  reference/AsarUSALTTPDisassembly/Bank0B.asm \
  --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d \
  --output /tmp/overworld-incbin-inventory.json
```

The JSON shape is specified by [the export schema](./schemas/incbin-inventory-export.schema.json).
When `--source-revision` is omitted, the output records `unspecified`; pass the
actual pinned source revision when producing an auditable inventory. Output
files are created exclusively and existing files are never overwritten.

## Important limitations

- This parser reads assembly text only. It does not open any `incbin` target
  path, read ROM bytes, execute Asar, or create build output.
- Address comments are treated as source annotations, not independently
  verified ROM offsets. The caller must use the correct pinned source file and
  check the address map.
- Only simple dollar-prefixed source address comments and labelled
  `incbin "path"` lines are supported. Unsupported forms should be reported
  rather than silently interpreted.
- This is an inventory helper, not a decoder. The included tests use synthetic
  source snippets and do not need a ROM.

The helper is exported from the extraction package alongside the
source-pointer-table parser. Both Python and CLI interfaces parse assembly text
only; neither resolves symbols or confirms the included payload bytes.

## Committed source inventories

The same parser powers the following registered metadata inventories:

- `music-payload-inventory`: 15 music `incbin` declarations from `Bank1B.asm`.
- `overworld-payloads-bank0b`: 164 overworld High/Low declarations from `Bank0B.asm`.
- `overworld-payloads-bank0c`: 84 overworld High/Low declarations from `Bank0C.asm`.
- `dungeon-room-payloads-bank03`: 34 room payload declarations from `Bank03.asm`.
- `dungeon-room-payload-inventory`: 75 room payload declarations from `Bank0A.asm`.
- `dungeon-room-payloads-bank1f`: 157 room payload declarations from `Bank1F.asm`.

Each inventory is source metadata only. The parser does not open include targets,
and the pinned disassembly does not track the referenced room binary payloads.
The three dungeon inventories collectively contain 266 uniquely labelled room
declarations. All have size annotations and start-offset comments, but no
explicit source-commented end offsets; `computed_file_offset_end` is arithmetic
from the start plus declared size and is not ROM-verified. The overworld exports
preserve their source-range mismatches rather than correcting them. See the
[extracted-data catalog](./extracted-data.md) and
[dungeon schema discovery note](./schemas/dungeons.md) for details and
regeneration commands.

## Audit registered inventories

Run `uv run zelda-suite audit-incbin-inventory` to summarize all registered `zelda-suite-incbin-inventory` assets. The version-1 JSON report lists missing source starts/sizes, explicit range-versus-size discrepancies, calculated candidate spans, and overlaps between those candidate spans. Use `--output PATH` to save a new report and `--fail-on-findings` for automation that should return status 1 when any diagnostic finding exists. See the [audit report schema](./schemas/incbin-inventory-audit.schema.json).

A candidate span is calculated as `source_file_offset_start` through `source_file_offset_start + declared_size_bytes - 1`. Overlaps and range mismatches identify annotations worth reviewing; they do not establish ROM offsets, payload contents, or which source annotation is correct. The audit reads committed metadata only, never opens `incbin` payloads, and never reads a ROM.


## Current registered audit baseline

The integration test for `zelda-suite audit-incbin-inventory` pins the current
manifest snapshot at the six inventories above and the pinned source revision.
The baseline contains 529 declarations: 525 have both a source start and size,
four have a metadata gap, and three declare a source-range/size discrepancy.
The calculated candidate spans produce ten overlap pairs, for 17 findings total
(counting each metadata gap, range mismatch, and pairwise candidate overlap).

This is a reproducibility baseline, not a claim that ten regions overlap in the
actual ROM. Candidate spans derive from source annotations; until they are
compared with a trusted local ROM and reconciled with the included data and
consumer code, findings must remain diagnostic. When source inventories
intentionally change, review the report and update the integration assertions
and this baseline in the same PR.
