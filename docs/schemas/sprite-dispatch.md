# Sprite handler dispatch table: source discovery

Status: **Phase 1 discovery; this is not the complete sprite catalog.**
The pinned source defines a local jump table for one range of sprite IDs. It is
useful for tracing behavior, but should not be confused with a full list of
sprite definitions, placement records, graphics, or statistics.

## Verified dispatch range

In the pinned
[`Bank1E.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Bank1E.asm),
`SpriteActive3_Table` is declared at file offsets
`$0F0B33–$0F0BBA`. The source comment gives that range an inclusive size of
`0x88` bytes; each `dw` handler pointer is two bytes, so the table contains
68 entries. The entries correspond to actual sprite type IDs `$79–$BC`
inclusive, not zero-based positions in the jump table.

The consumer `SpriteActive3_Main` reads the active sprite's type from
`$0E20,X`, subtracts `$79`, multiplies the result by two, indexes
`SpriteActive3_Table`, and dispatches to the selected handler. This is a
local code dispatch mechanism; it is not the ROM's global sprite-ID index or
the sprite's per-type statistics table.

## Aliased handlers are meaningful

The table intentionally maps multiple sprite IDs to the same handler. Examples
from the source include:

| Sprite ID(s) | Handler label | Source-commented cases |
| --- | --- | --- |
| `$7E–$7F` | `Sprite_GuruguruBar` | Swinging fireball chains |
| `$83–$84` | `Sprite_Eyegore` | Green and red Eyegores |
| `$95–$98` | `Sprite_LaserEye` | Several Laser Eye types |
| `$A5–$A6` | `Sprite_Zazak` | Blue and red Zazaks |
| `$A8–$A9` | `Sprite_Bomber` | Two Bomber variants |
| `$AE–$B1` | `Sprite_Pipe` | Pipe directions |

Consequently, the handler label is not a unique sprite identity. An authoring
model should preserve the original numeric sprite type ID and may expose the
handler association as implementation metadata, but must not replace the ID
with the handler name.

Some source comments include tentative names or questions (for example, a
commented “maybe?”). Preserve such text as source notes, not verified display
names. The source itself also warns that the indices written in the table
comments are actual sprite values, not the table's zero-based element indices.

## Audit-friendly record

An initial source inventory for this dispatch table should preserve:

| Field | Meaning |
| --- | --- |
| `sprite_type_id` | Actual sprite ID from the source comment, `$79–$BC` |
| `table_index` | Zero-based position, `sprite_type_id - 0x79` |
| `pointer_entry_file_offset` | `0x0F0B33 + table_index * 2` |
| `handler_expression` | Exact `dw` expression from source |
| `handler_label` | Parsed handler label |
| `source_comment` | Original comment, including any uncertainty |
| `source_revision` | Pinned revision `347c23f9fc019c72d32da537c9cb235f468d021d` |

The dispatch table only covers the ID range handled by this routine. The rest
of the sprite domain must be inventoried from its own dispatch/initialization
path; do not extrapolate these 68 entries into a full catalog.

## Validation gates

1. Compare each source table pointer with the corresponding assembled code
   address under the pinned mapping; source comments alone do not prove the
   routine target is correct.
2. Keep `sprite_type_id` separate from `table_index` and from the handler
   label in JSON/SQLite.
3. Trace the other sprite dispatch paths before claiming complete sprite
   coverage, and cross-reference sprite statistics/graphics tables separately.
4. Use synthetic tests for parsing table comments and aliases; verify all ROM
   addresses against a local clean US ROM or matching disassembly build when
   that becomes available.

This note records source declarations only and does not read or modify ROM
bytes or claim sprite editing is implemented.

## Committed source inventory

The source inventory is now committed as
[`data/extracted/sprite-active3-dispatch.json`](../../data/extracted/sprite-active3-dispatch.json)
and registered as `sprite-active3-dispatch` in
[`data/extracted/manifest.json`](../../data/extracted/manifest.json). Each record
keeps the actual sprite type ID separate from the zero-based `table_index`,
preserves the `dw` handler label, and stores the raw source comment alongside
the comment's handler-address annotation and description.

Regenerate it using the pinned source:

```bash
uv run zelda-suite inspect-sprite-dispatch \
  reference/AsarUSALTTPDisassembly/Bank1E.asm \
  --table-offset '$0F0B33' \
  --table-end-offset '$0F0BBA' \
  --sprite-id-start '$79' \
  --entry-count 68 \
  --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d \
  --output /tmp/sprite-active3-dispatch.json
uv run zelda-suite validate-source-export /tmp/sprite-active3-dispatch.json
diff -u data/extracted/sprite-active3-dispatch.json /tmp/sprite-active3-dispatch.json
```

The JSON export schema is
[`sprite-dispatch-export.schema.json`](./sprite-dispatch-export.schema.json).
CI checks that the committed 68 records match the pinned source parser exactly.
Handler labels that appear more than once remain separate table slots, since
different sprite IDs may intentionally share one implementation. The source
comment addresses remain annotations and are not resolved to ROM file offsets.
