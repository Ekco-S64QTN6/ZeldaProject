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

The helper lives in the extraction package but intentionally does not update
any existing CLI or package initializer. That keeps this contribution
merge-order independent of the pointer-table parser PR; a future CLI can
consume it once the extraction APIs settle.
