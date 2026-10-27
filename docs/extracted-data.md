# Committed source-derived data

The first committed Phase 1 table export lives at `data/extracted/falling-prize-item-values.json`. It contains a source-level inventory of `Pool_AddPendantOrCrystal.item_values` from the pinned Asar disassembly; it is not a ROM byte slice and does not represent every item source in the game.

## Provenance

- Source: `Ancilla/ancilla_init.asm` in `AsarUSALTTPDisassembly` revision `347c23f9fc019c72d32da537c9cb235f468d021d`.
- Table: local label `.item_values` inside `Pool_AddPendantOrCrystal`, bounded by `.fall_height`.
- Headerless file offset: `$048B90` through `$048B96`.
- Element width/count: seven `db` values, one byte each.
- Recorded values: `$10`, `$37`, `$39`, `$38`, `$26`, `$0F`, `$20`.

Each row keeps its original expression, source label, source line, table index, calculated source file offset, literal integer, and pinned revision. The shared source-export loader validates the output format and offset/width invariants.

## Reproduce and review

From the repository root, run:

```bash
uv run zelda-suite inspect-data-table \
  reference/AsarUSALTTPDisassembly/Ancilla/ancilla_init.asm \
  .item_values \
  --table-offset '$048B90' \
  --directive db \
  --parent-label Pool_AddPendantOrCrystal \
  --end-label .fall_height \
  --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d \
  --output /tmp/falling-prize-item-values.json
uv run zelda-suite validate-source-export /tmp/falling-prize-item-values.json
diff -u data/extracted/falling-prize-item-values.json /tmp/falling-prize-item-values.json
```

The CLI intentionally refuses to overwrite output files. Generate to a temporary path, inspect the diff, then update the checked-in JSON only after reviewing the source revision, table boundary, and entry offsets.

CI loads the committed export and compares its entry list to the output of the parser against the pinned source. ROM files and binary ROM slices are not needed.
