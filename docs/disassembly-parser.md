# Disassembly source-table inspection

The `zelda-suite inspect-pointer-table` command parses a named brace-delimited
Asar `dl` table and prints an audit-oriented JSON representation. It reads
assembly source only: it does not read ROM bytes, execute Asar, evaluate
symbols, or resolve pointer targets.

## Example: dungeon room object pointers

With the pinned disassembly submodule checked out:

```bash
uv run zelda-suite inspect-pointer-table \
  reference/AsarUSALTTPDisassembly/Bank1F.asm \
  RoomData_ObjectDataPointers \
  --table-offset '$0F8000' \
  --output /tmp/room-object-pointers.json
```

The command defaults to the repository's pinned disassembly revision
`347c23f9fc019c72d32da537c9cb235f468d021d`. Use `--source-revision` when
inspecting another revision so the JSON records which source was parsed.

The output includes:

- `table_label`, `table_file_offset`, `entry_width`, and `entry_count`.
- For each entry: zero-based table index, calculated location of the pointer
  entry, source line, original pointer expression, target label, addend,
  explicit empty-target flag, and source revision.
- A stable key ordering, UTF-8 encoding, and final newline for easy diffing.

The default three-byte entry width reflects Asar's `dl` data directive in this
pointer table; `--entry-width` can override it when a separate source table is
known to have another encoding. The table offset is an input supplied by the
caller and must be verified against source comments and the canonical offset
map; the command does not infer that offset by parsing comments.

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
