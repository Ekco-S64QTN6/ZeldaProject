# Source scalar data-table inspection

The `zelda-suite inspect-data-table` command exports a bounded run of Asar `db`, `dw`, or `dl` values as an audit-friendly JSON file. It reads source text only: it does not open incbin payloads, evaluate assembler expressions, read ROM bytes, or modify the ROM.

## Example: falling-prize item values

```bash
uv run zelda-suite inspect-data-table \
  reference/AsarUSALTTPDisassembly/Ancilla/ancilla_init.asm \
  Pool_AddPendantOrCrystal.item_values \
  --table-offset '$048B90' \
  --directive db \
  --entry-count 7 \
  --stop-before-label .fall_height \
  --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d \
  --output /tmp/falling-prize-items.json
uv run zelda-suite validate-source-export /tmp/falling-prize-items.json
```

The seven source bytes are `$10`, `$37`, `$39`, `$38`, `$26`, `$0F`, and `$20`. The source labels identify Ether, the three pendants, a heart container, Bombos, and a crystal. The output preserves the raw expressions and labels; this small table is not a global item catalog.

## Bounded parsing

`--entry-count` is mandatory, so the parser does not infer a table's length by consuming adjacent directives. When parsing a local label inside a parent block, use a known `--stop-before-label` boundary when available. The parser verifies the expected count at that boundary and errors if additional values appear before it.

Each entry includes its zero-based index, calculated source file offset, assembly source line, directive, most recent source label, raw expression, numeric value when the expression is a simple literal, inline comment, and source revision. Expressions such as `SomeConstant` or `$03+$01` remain unevaluated with a null numeric value.

The output shape is specified by [the version-1 JSON Schema](./schemas/data-table-export.schema.json), and the existing source-export loader validates the field types, entry count, source revision, directive width, and offset sequence.

## Boundaries

The supplied table offset must be verified by the caller against the pinned source's address comments or another trusted offset map. This command does not extract the referenced ROM bytes or resolve source labels to addresses. For actual extraction, use the approved local ROM workflow and keep ROM images and ROM-derived byte slices out of Git.
