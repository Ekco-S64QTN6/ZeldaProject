# Raw Asar data-table inspection

The `zelda-suite inspect-data-table` command exports source-level `db`,
`dw`, or `dl` expressions into a stable version-1 JSON record. Numeric
literals are additionally exposed as integers; unresolved expressions are
preserved verbatim and are never evaluated.

## Example: falling-prize item values

With the pinned disassembly submodule checked out:

```bash
uv run zelda-suite inspect-data-table \
  reference/AsarUSALTTPDisassembly/Ancilla/ancilla_init.asm \
  .item_values \
  --table-offset '$048B90' \
  --directive db \
  --parent-label Pool_AddPendantOrCrystal \
  --end-label .fall_height \
  --entry-count 7 \
  --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d \
  --output /tmp/falling-prize-item-values.json

uv run zelda-suite validate-source-export /tmp/falling-prize-item-values.json
```

The parser uses the parent block to scope local labels such as `.item_values`;
the end label is exclusive, so the adjacent `.fall_height` table is not mixed
into the item-value table. The caller supplies the verified file offset. The
tool does not infer offsets from the comments.

The pinned source yields seven one-byte values at `$048B90–$048B96`:
`$10, $37, $39, $38, $26, $0F, $20`. The export preserves source labels and
the original expression for each value. Use the labels as provenance, not as a
claim that the table covers every item source in the game.

## Supported table boundaries

Use `--parent-label` when the requested label is local or might occur more
than once. Use `--end-label` when multiple adjacent arrays live inside the
same parent block. If no end label is supplied, a global brace-delimited table
is bounded by its braces; other forms are bounded at the next global label.
Ambiguous local labels fail instead of silently selecting the wrong table.
Use optional `--entry-count N` when the expected size is independently known;
the command fails if the bounded parser returns any other number of entries.
This catches accidentally truncated or overlong tables without evaluating
assembler expressions. The option is an assertion, not a way to infer a
table's boundary.

The directive determines the legal literal range and default storage width:
`db` is one byte, `dw` is two, and `dl` is three. `--entry-width` only
overrides the calculated file-offset stride for a documented custom layout; it
does not change the range of values allowed by the directive.

The JSON contract is [data-table-export.schema.json](./schemas/data-table-export.schema.json).
The asset loader validates the format version, record count, source revision,
entry offsets, and literal-width invariants.

By default, `inspect-data-table` emits format version 1 and omits inline comments.
Use `--include-comments` to opt into version 2:

```bash
uv run zelda-suite inspect-data-table \
  reference/AsarUSALTTPDisassembly/Ancilla/ancilla_init.asm \
  .item_values \
  --table-offset '$048B90' \
  --directive db \
  --parent-label Pool_AddPendantOrCrystal \
  --end-label .fall_height \
  --entry-count 7 \
  --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d \
  --include-comments \
  --output /tmp/falling-prize-item-values-v2.json
uv run zelda-suite validate-source-export /tmp/falling-prize-item-values-v2.json
```

Version 2 adds `inline_comment` to each entry. The value is the text after
the source line's semicolon with surrounding whitespace stripped; it is
`null` when the line has no semicolon. When a line supplies multiple `db`,
`dw`, or `dl` values, each emitted entry carries the same line comment.
Comments remain annotations only: neither the parser nor the validator treats
them as executable expressions or verified semantic definitions. The schema is
[here](./schemas/data-table-export-v2.schema.json). Existing version-1 exports
and committed assets remain unchanged.

## Safety and limitations

This command parses assembly text only. It does not read ROM bytes, open
`incbin` payloads, execute Asar, resolve symbol expressions, or write ROMs.
The table file offset and the source revision are caller-supplied provenance
and should be verified against the exact source revision and offset map. The
parser is a raw-table foundation, not a semantic item catalog or an editor.


## Audit unresolved expressions without a ROM

Use `uv run zelda-suite audit-unresolved-table-expressions` to enumerate unresolved expressions across all registered scalar data-table exports. The report includes each raw expression, table index, source line, file offset, and a conservative syntax-shape classification. Bare negative decimal literals are counted separately because `verify-rom-tables` already handles their bounded two's-complement encoding; other unresolved expressions are never evaluated or guessed.

Use `--output PATH` to save a new JSON report, or `--fail-on-unresolved` for CI/workflows that should return status 1 when any unresolved expressions remain. This command reads committed source metadata only; it does not need a ROM, execute Asar, or read payload bytes. The report contract is [source-expression-audit.schema.json](./schemas/source-expression-audit.schema.json).


## Current registered expression-audit baseline

The integration test pins the current 16 registered `zelda-suite-data-table`
assets (689 entries, all from disassembly revision
`347c23f9fc019c72d32da537c9cb235f468d021d`). The current metadata contains 514
direct numeric literals, 77 bare negative decimal literals, and 98 unresolved
expressions. Those 98 unresolved records are all classified as simple symbols
and belong to `text-dictionary-pointers`; they remain raw symbols and were not
resolved or evaluated. The 77 negative decimal literals are counted separately
because the ROM verifier can compare their bounded two's-complement encodings.

These counts describe the committed source exports, not bytes checked against a
ROM. Update the baseline and this section together when source exports
intentionally change, after reviewing the diff and their source-parity tests.
