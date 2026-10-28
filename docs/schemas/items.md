# Items and chest-data discovery

This page documents one source inventory, not a complete editable item/chest/shop
schema. The registered [`dungeon-chest-data`](../../data/extracted/dungeon-chest-data.json)
asset preserves the 168 packed three-byte `dl` records under
`Dungeon_ChestData` in the pinned `Bank01.asm` revision.

## Packed record fields

The pinned source comments define the 24-bit record shape:

- The top byte is the raw item value to give.
- The low 15 bits are the room value.
- Bit 15 (`0x8000`) marks a big-chest entry.

The source consumer walks entries in three-byte steps, finds the current room's
matching record, uses the top byte as the item value, and tests bit 15 to take
the big-chest path. The inventory keeps raw values and original expressions; it
does not map item bytes to names, infer shop inventory, or assert the commented
range `$00E96E-$00EB65` as a verified ROM/file offset.

## Standard shopkeeper purchase-handler catalog

The registered [`shop-item-handlers`](../../data/extracted/shop-item-handlers.json)
export preserves seven purchase handlers selected by IDs `$07–$0D` in
`Sprite_ShopKeeper`. The source-coded price literals in A/Y combine to
150, 50, 500, 10, 30, 50, and 10; the handlers pass receipt indexes 46, 4, 5,
66, 68, 49, and 14 to `ShopItem_HandleReceipt`.

The audit joins these indexes to the matching rows in `item-receipt-layout`
by `table_index`. The resulting raw fields (including item value, target
address, flags, properties and offsets) are preserved without converting the
slot index to a canonical item ID. Comments describing handler addresses remain
unverified, and the exact inline-dispatch table offset is not established from
the containing routine range annotation.

Run:

```bash
uv run zelda-suite audit-shop-item-handlers
uv run zelda-suite audit-shop-item-handlers --output /tmp/shop-item-handlers-audit.json
```

This is a purchase-handler catalog, not a room-specific shop-stock table. It
does not establish where each handler is used in the game, verify its price
behavior against ROM execution, or resolve receipt slots to semantic item
names. The strict schemas are
[`shop-item-handlers-export.schema.json`](./shop-item-handlers-export.schema.json)
and [`shop-item-handlers-audit.schema.json`](./shop-item-handlers-audit.schema.json).

## Potion-shop transaction catalog

The registered [`potion-shop-transactions`](../../data/extracted/potion-shop-transactions.json)
export preserves three priced handlers from pinned `Sprites/sprite_potion_shop.asm`:
`Sprite_GreenPotionItem`, `Sprite_BluePotionItem`, and `Sprite_RedPotionItem`.
Their source rupee-balance comparisons and deductions use `$003C` (60),
`$00A0` (160), and `$0078` (120). Each handler block also includes a call to
`Sprite_GetEmptyBottleIndex` and passes a selector to `Link_ReceiveItem`:
`$2F`, `$30`, and `$2E`.

Run:

```bash
uv run zelda-suite inspect-potion-shop-transactions reference/AsarUSALTTPDisassembly/Sprites/sprite_potion_shop.asm --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d --entry-count 3 --output /tmp/potion-shop-transactions.json
uv run zelda-suite validate-source-export /tmp/potion-shop-transactions.json
diff -u data/extracted/potion-shop-transactions.json /tmp/potion-shop-transactions.json
uv run zelda-suite audit-potion-shop-transactions
```

The audit joins the receipt selectors to dense `item-receipt-layout` positions
and includes the matching raw graphics-table comments. The selectors correspond
to source-comment labels `POTION REFILL (GREEN)`, `POTION REFILL (BLUE)`, and
`POTION REFILL (RED)`. These labels are annotations, not canonical item IDs.
The audit does not read ROM bytes, verify price behavior at runtime, or determine
which potion transactions are stocked in particular rooms. See the
[potion transaction export schema](./potion-shop-transactions-export.schema.json)
and [audit schema](./potion-shop-transactions-audit.schema.json).

## Bomb Shop and Bottle Vendor transactions

The registered [`special-shop-transactions`](../../data/extracted/special-shop-transactions.json) export adds three source-coded purchase paths. Both Bomb Shop handlers pass `$64/$00` as their price bytes (100 rupees) to the payment helper. The Bomb Shop Bomb then uses receipt selector `$28`; the Super Bomb instead writes `$0D` to `$7EF3CC` and spawns a tagalong, so its receipt selector is intentionally null.

The Bottle Vendor flow compares the wallet balance with `$0064`, grants the bottle through `Link_ReceiveItem` with selector `$16`, and deducts `$0064`. Its source annotation `\item(Bottle)` is preserved as a source comment, not promoted to a canonical item ID.

Run:

```bash
uv run zelda-suite inspect-special-shop-transactions reference/AsarUSALTTPDisassembly/Sprites/sprite_bomb_shop_entity.asm reference/AsarUSALTTPDisassembly/Sprites/sprite_bottle_vendor.asm --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d --entry-count 3 --output /tmp/special-shop-transactions.json
uv run zelda-suite validate-source-export /tmp/special-shop-transactions.json
diff -u data/extracted/special-shop-transactions.json /tmp/special-shop-transactions.json
uv run zelda-suite audit-special-shop-transactions
```

The audit cross-references only receipt selectors `$28` and `$16` against raw `item-receipt-layout` entries and their graphics comment annotations. It reports no canonical semantic item IDs, room-specific shop stock, runtime price validation, or verified ROM offsets. The Super Bomb reward remains a separate state-flag/tagalong action. See the [export schema](./special-shop-transactions-export.schema.json) and [audit schema](./special-shop-transactions-audit.schema.json).

## Receive-item graphics comment annotations

The registered `item-receipt-graphics-indices` table has 76 dense entries, indexed
by its position from `$00` through `$4B`. Source comments identify slots
`$00–$3F`, then resume at comment ID `$41`; the comment ID `$40` is absent.
Consequently, table positions `$40–$4B` retain source comment IDs `$41–$4C`.
The source-derived audit preserves this discrepancy and does not rewrite either
the table indexes or the comments.

Run:

```bash
uv run zelda-suite audit-item-receipt-annotations
uv run zelda-suite audit-item-receipt-annotations --output /tmp/item-receipt-annotation-audit.json
```

The audit reports 76 parsed comments, 64 comment IDs equal to their dense table
indexes, 12 mismatches (all with a +1 delta), and missing source-comment ID
`$40`. These are annotations in pinned source, not canonical item IDs or
verified runtime item names. The shop-handler audit now shows the raw graphics
expression, comment ID, comment label, and mismatch flag for each positional
receipt selector; in particular, selectors `$42` and `$44` point to entries
whose comments say `0x43 - HEART` and `0x45 - 10 ARROWS`. No automatic
renumbering or semantic correction is applied.

See the [annotation audit schema](./item-receipt-annotation-audit.schema.json)
and the [shop-handler audit schema](./shop-item-handlers-audit.schema.json).

## Source-only audit

Run:

```bash
uv run zelda-suite audit-dungeon-chest-data
uv run zelda-suite audit-dungeon-chest-data --output /tmp/dungeon-chest-audit.json
```

The audit reports 168 records, 106 unique room values, 32 repeated room-value
groups, 11 big-chest flags, 157 entries without that flag, and 33 distinct raw
item values. Repeated room values are retained because the source consumer
iterates among multiple chest records for the same room.

The versioned schemas are
[`dungeon-chest-data-export.schema.json`](./dungeon-chest-data-export.schema.json)
and [`dungeon-chest-data-audit.schema.json`](./dungeon-chest-data-audit.schema.json).

Remaining work includes resolving raw item values to a semantic item catalog,
connecting chest records and purchase handlers to editable room/chest/shop
placements, validating source offsets against a trusted ROM, and reconciling the
source formats with a verified writer or YAZE/z3ed round-trip.
