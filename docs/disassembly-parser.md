# Disassembly source-table inspection

The `zelda-suite inspect-pointer-table` command parses a named brace-delimited
Asar `dw` or `dl` pointer table and prints an audit-oriented JSON representation. It reads
assembly source only: it does not read ROM bytes, execute Asar, evaluate
symbols, or resolve pointer targets.

## Example: dungeon room object pointers

With the pinned disassembly submodule checked out:

```bash
uv run zelda-suite inspect-pointer-table \
  reference/AsarUSALTTPDisassembly/Bank1F.asm \
  RoomData_ObjectDataPointers \
  --table-offset '$0F8000' \
  --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d \
  --output /tmp/room-object-pointers.json
```

The example explicitly records the repository's pinned disassembly revision
`347c23f9fc019c72d32da537c9cb235f468d021d`. For arbitrary source files, the
command records `unspecified` unless `--source-revision` is supplied; it
cannot prove a file's Git revision from the source text alone. Always record the
revision you actually inspected when producing an auditable export.

The output format is specified by [the JSON Schema](./schemas/pointer-table-export.schema.json). The schema describes field types and basic invariants; table-index sequencing and offset arithmetic are documented semantic constraints checked by the parser/tests rather than by JSON Schema.

The output includes:

- `table_label`, `table_file_offset`, `entry_width`, and `entry_count`.
- For each entry: zero-based table index, calculated location of the pointer
  entry, source line, original pointer expression, target label, addend,
  explicit empty-target flag, and source revision.
- A stable key ordering, UTF-8 encoding, and final newline for easy diffing.

The default entry width follows the selected directive: `dl` uses three-byte
entries and `dw` uses two-byte entries. Use `--directive dw` for word-pointer
tables such as `OverworldData_HiddenItems` at `$0DC2F9`. The optional
`--entry-width` can override calculated entry locations for a documented custom
encoding, but it does not alter how expressions are parsed. The table offset is
an input supplied by the caller and must be verified against source comments
and the canonical offset map; the command does not infer it from comments.

## Safety and limitations

- Source expressions are preserved; they are not executed or evaluated.
- Computed pointer-entry locations are not target addresses.
- No attempt is made to convert an Asar long pointer or symbol expression into
  a ROM file offset.
- Unsupported expression syntax fails loudly rather than silently dropping an
  entry.
- `--output` creates a new file and refuses to overwrite an existing one.
- Synthetic tests are independent of ROMs. Full extraction still requires a
  local clean US ROM and fixtures that verify parsed entries against its bytes.

This is a building block for Phase 1 extraction, not a full room extractor.


## Example: overworld hidden-item area pointers

The pinned `Bank1B.asm` declares a 128-entry `dw` table at file offset
`$0DC2F9`. To export the source expressions without resolving their targets:

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

The export records a two-byte offset stride and the original `dw` expressions.
It does not decode the pointed-to hidden-item records or establish record
boundaries; see [the hidden-item discovery note](./schemas/overworld-hidden-items.md).
