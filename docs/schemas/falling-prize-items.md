# Falling-prize item lookup: source discovery

Status: **Phase 1 discovery, not a general inventory of all item sources.**
The pinned disassembly defines a compact, source-backed lookup for items
spawned by the falling-prize routine. This is a useful first item-table fixture
candidate because both the data labels and a consumer are visible in the source.

## Source-declared table (ROM verification pending)

In the pinned
[`Ancilla/ancilla_init.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Ancilla/ancilla_init.asm),
`Pool_AddPendantOrCrystal` is declared at file offsets
`$048B90–$048BC0`. Its `.item_values` subtable starts at `$048B90` and has
seven one-byte entries, matching the
[`Zelda_3_ROM.log`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Logs/Zelda_3_ROM.log)
description of `$048B90–$048B96` as a seven-entry item-value table indexed
from 0 through 6.

| Index | Source-annotated offset | Source label | Raw byte | Source meaning |
| ---: | --- | --- | ---: | --- |
| 0 | `$048B90` | `.ether_medallion` | `$10` | Ether medallion |
| 1 | `$048B91` | `.pendants[0]` | `$37` | Green pendant |
| 2 | `$048B92` | `.pendants[1]` | `$39` | Red pendant |
| 3 | `$048B93` | `.pendants[2]` | `$38` | Blue pendant |
| 4 | `$048B94` | `.heart_container` | `$26` | Heart container |
| 5 | `$048B95` | `.bombos_medallion` | `$0F` | Bombos medallion |
| 6 | `$048B96` | `.crystal` | `$20` | Crystal |

The offsets and values above follow the pinned source declarations and source
annotations. They have **not** been independently checked against bytes from a
locally supplied ROM. Names and values are recorded as the disassembly
identifies them; this does not claim that every chest or dropped-item source
uses this lookup.

## Consumer evidence

The source consumer is `AddPendantOrCrystal` (special-effect argument `A=$29`,
described in the source as “pendants/crystals, etc.”). It saves the incoming
index from `X` to `$02D8`, loads that index into `Y`, then reads
`Pool_AddPendantOrCrystal_item_values, Y`. It also indexes adjacent tables
for fall height, X/Y offsets, and delay timers. The source separately defines
`AddReceivedItem` for special effect `$22`; do not conflate these routines or
treat this seven-entry lookup as a global item catalog. See the pinned
[`Ancilla/ancilla_init.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Ancilla/ancilla_init.asm).

The surrounding `Pool_AddPendantOrCrystal` region defines four more
parallel arrays. These values are retained as source-declared data, not as
ROM-verified facts:

| Array | Source-annotated range | Directive / count | Raw source values |
| --- | --- | --- | --- |
| `.fall_height` | `$048B97–$048B9D` | `db`, 7 bytes | `$60, $80, $80, $80, $80, $80, $80` |
| `.y_offsets` | `$048B9E–$048BAB` | `dw`, 7 words | `$0048, $0078, $0078, $0078, $0078, $0068, $0078` |
| `.x_offsets` | `$048BAC–$048BB9` | `dw`, 7 words | `$0078, $0078, $0078, $0078, $0078, $0080, $0078` |
| `.delay_timers` | `$048BBA–$048BC0` | `db`, 7 bytes | `$40, $00, $00, $00, $00, $FF, $00` |

The `AddPendantOrCrystal` consumer uses the same selector index to read the
item-value, fall-height, Y-offset, X-offset, and delay-timer arrays. The
combined source view is therefore:

| Index | Item label | Item value | Fall height | Y offset (raw word) | X offset (raw word) | Delay timer |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 0 | `.ether_medallion` | `$10` | `$60` | `$0048` | `$0078` | `$40` |
| 1 | `.pendants[0]` | `$37` | `$80` | `$0078` | `$0078` | `$00` |
| 2 | `.pendants[1]` | `$39` | `$80` | `$0078` | `$0078` | `$00` |
| 3 | `.pendants[2]` | `$38` | `$80` | `$0078` | `$0078` | `$00` |
| 4 | `.heart_container` | `$26` | `$80` | `$0078` | `$0078` | `$00` |
| 5 | `.bombos_medallion` | `$0F` | `$80` | `$0068` | `$0080` | `$FF` |
| 6 | `.crystal` | `$20` | `$80` | `$0078` | `$0078` | `$00` |

This joined view makes index alignment explicit without assigning units to the
raw offset words or normalizing `$FF` into a semantic timer value. Each array
retains its own element width and meaning; source offsets and values still
require local-ROM verification before being treated as confirmed ROM facts.

## Suggested extraction record

For an initial read-only extraction, retain the source trace on every row:

| Field | Meaning |
| --- | --- |
| `item_index` | Integer index in the seven-entry table, `0–6` |
| `file_offset` | Source-annotated offset, `0x048B90 + item_index`; not independently ROM-verified |
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
3. The pinned-source tests already check the five arrays' seven-entry counts,
   offsets, widths, shared index range, and source parser parity. Compare their
   corresponding bytes against a trusted local US ROM before claiming
   ROM-verified extraction or exposing a writable schema.
4. Keep any ROM and ROM-derived binary fixtures local and out of Git.

This is documentation only; it reads no ROM bytes and changes none.
