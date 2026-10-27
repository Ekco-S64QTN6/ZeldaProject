# Falling-prize item lookup: source discovery

Status: **Phase 1 discovery, not a general inventory of all item sources.**
The pinned disassembly defines a compact, source-backed lookup for items
spawned by the falling-prize routine. This is a useful first item-table fixture
candidate because both the data labels and a consumer are visible in the source.

## Verified table

In the pinned
[`Ancilla/ancilla_init.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Ancilla/ancilla_init.asm),
`Pool_AddPendantOrCrystal` is declared at file offsets
`$048B90–$048BC0`. Its `.item_values` subtable starts at `$048B90` and has
seven one-byte entries, matching the
[`Zelda_3_ROM.log`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Logs/Zelda_3_ROM.log)
description of `$048B90–$048B96` as a seven-entry item-value table indexed
from 0 through 6.

| Index | File offset | Source label | Stored byte | Source meaning |
| ---: | --- | --- | ---: | --- |
| 0 | `$048B90` | `.ether_medallion` | `$10` | Ether medallion |
| 1 | `$048B91` | `.pendants[0]` | `$37` | Green pendant |
| 2 | `$048B92` | `.pendants[1]` | `$39` | Red pendant |
| 3 | `$048B93` | `.pendants[2]` | `$38` | Blue pendant |
| 4 | `$048B94` | `.heart_container` | `$26` | Heart container |
| 5 | `$048B95` | `.bombos_medallion` | `$0F` | Bombos medallion |
| 6 | `$048B96` | `.crystal` | `$20` | Crystal |

The offsets and byte values above follow the `db` declarations at those source
labels. Names and values are recorded as the disassembly identifies them; this
does not claim that every possible chest or dropped-item source uses this
lookup.

## Consumer evidence

The source consumer is `AddPendantOrCrystal` (special-effect argument `A=$29`,
described in the source as “pendants/crystals, etc.”). It saves the incoming
index from `X` to `$02D8`, loads that index into `Y`, then reads
`Pool_AddPendantOrCrystal_item_values, Y`. It also indexes adjacent tables
for fall height, X/Y offsets, and delay timers. The source separately defines
`AddReceivedItem` for special effect `$22`; do not conflate these routines or
treat this seven-entry lookup as a global item catalog. See the pinned
[`Ancilla/ancilla_init.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Ancilla/ancilla_init.asm).

The surrounding `Pool_AddPendantOrCrystal` region also documents these
associated per-index arrays:

- `.fall_height` begins at `$048B97` and contains seven bytes.
- `.y_offsets` begins at `$048B9E`.
- `.x_offsets` begins at `$048BAC`.
- `.delay_timers` follows later within the same declared region.

These arrays share the index domain, but each has its own element type and
meaning. Do not collapse them into the item value byte or infer the full array
lengths from the labels alone.

## Suggested extraction record

For an initial read-only extraction, retain the source trace on every row:

| Field | Meaning |
| --- | --- |
| `item_index` | Integer index in the seven-entry table, `0–6` |
| `file_offset` | Verified source offset, `0x048B90 + item_index` |
| `source_label` | Exact label associated with this entry |
| `item_value_byte` | Raw stored byte, preserved as an integer `0–255` |
| `source_description` | Human-readable source comment, when present |
| `source_revision` | Pinned disassembly revision `347c23f9fc019c72d32da537c9cb235f468d021d` |

Prefer a narrow `falling_prize_item` table or namespace over an entity named
simply `items`. Other game systems (chests, shops, overworld secrets, sprite
drops, inventory IDs) may use different tables or transformations and must be
mapped independently.

## Validation gates

1. Compare the seven source bytes with the corresponding bytes in a locally
   supplied clean US ROM before marking extraction as verified.
2. Exercise every index through the source consumer in a controlled local
   fixture or test setup; preserve raw values even if an index is not currently
   used by normal gameplay.
3. Trace adjacent per-index arrays separately and establish their lengths from
   source and consumer bounds before exposing them in a schema.
4. Keep any ROM and ROM-derived binary fixtures local and out of Git.

This is documentation only; it reads no ROM bytes and changes none.
