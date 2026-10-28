
# Sprites and OAM allocator discovery

This page records one source-discovery result, not a complete editable sprite
schema. The registered [`oam-buffer-position-table`](../../data/extracted/oam-buffer-position-table.json)
export preserves the 54 `dw` entries under `Pool_OAM_GetBufferPosition` in the
pinned `Sprites/sprite_oam_allocation.asm` source.

## Registered table

The source comment marks `$06BA9E–$06BB09`, a 108-byte span containing six
`.limits` words and 48 `.fallback_points` words, eight per region.

The entry points `OAM_AllocateFromRegionA` through `OAM_AllocateFromRegionF`
set Y to `$00`, `$02`, `$04`, `$06`, `$08`, and `$0A`.
`OAM_GetBufferPosition` indexes `.limits` by that selector. On overflow,
the source stores the selector in `$0C`, reduces the per-region counter to
one of eight slots, doubles that slot to obtain a byte offset, then indexes the
fallback table using `($0C * 8) + byte_offset`. The audit presents the entries
using those source-derived relationships; it does not execute the allocator.

Run:

```bash
uv run zelda-suite audit-oam-allocation
uv run zelda-suite audit-oam-allocation --output /tmp/oam-allocation-audit.json
```

## Evidence limits

The committed export and audit report are based on source metadata. They do not
validate `$06BA9E–$06BB09` against a locally supplied ROM, verify actual OAM
buffer contents, show rendered sprites, or establish the relationship between
sprite IDs, graphics banks, placements, and semantic game objects. Those remain
open Phase 0/Phase 1 work.

The report schema is [`oam-allocation-audit.schema.json`](./oam-allocation-audit.schema.json).
