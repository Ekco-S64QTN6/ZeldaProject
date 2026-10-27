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
