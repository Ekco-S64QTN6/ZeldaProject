# ROM writer

`src/zelda_suite/write/` is the only code that produces ROM bytes (CLAUDE.md §7 rule 1).
It turns a project's edits into a **new** ROM file; the base image is read through the
extraction layer and never modified.

```bash
uv run zelda-suite build-rom project/my-hack.db \
    --base-rom "base_game_roms/Legend of Zelda, The - A Link to the Past (U) [!].smc" \
    --output project/my-hack.sfc            # dry run: the full report, nothing written
uv run zelda-suite build-rom ... --apply    # write project/my-hack.sfc
uv run zelda-suite build-rom ... --apply --overwrite
```

Python: `zelda_suite.write.build_rom(db, base_rom, output, dry_run=True, overwrite=False)`.

## What it writes

Only records whose offsets are proven against the US image, each as an in-place,
same-size patch:

| Domain | Record | Offset | Evidence |
|:--|:--|:--|:--|
| Dungeon chests (`Dungeon_ChestData`, Bank01) | 3 bytes, the packed 24-bit literal little-endian (room word with bit 15 = big chest, then the item byte) | `$00E96E + 3 × index` | All 168 source literals matched the fingerprint-matched US ROM byte-for-byte (2026-10-31) |
| Overworld hidden items (Bank1B) | 3 bytes: coordinate word little-endian, value byte | the record's declaration-stream offset, inside `$0DC3F9–$0DC89C` | `verify-overworld-hidden-items`: 550 comparisons, zero mismatches |

The SNES header checksum (`$7FDE`, complement `$7FDC`; LoROM, the 16-bit sum of all
bytes with those four bytes taken as `FF FF 00 00`) is recomputed. The routine
reproduces the US image's stored `$AF0D/$50F2`.

## What it refuses

Nothing is written when any of these holds:

- the base image is not 1 MiB (headerless US);
- a record's **source baseline** bytes differ from the base image at its offset — a
  different ROM, a different revision, or an offset this layer has wrong;
- a patch changes size, leaves its table, or overlaps another;
- the project has **project-authored hidden items**: adding records means growing the
  Bank1B table, which an in-place patch cannot do (relocation is future work);
- the output path is the base image, or an existing file without `--overwrite`;
- after patching, any byte outside the patches and the checksum differs (an internal
  consistency check against the byte diff).

## The report

`format: zelda-suite-rom-build`, version 1: `dry_run`, base and output SHA-256, each
patch with its old/new bytes and **citation** (project table and row, disassembly file
and line, source revision, before/after field values), the header checksum before and
after, the full byte diff (`zelda-suite-rom-diff` regions) and `written`.

## Verification status

- Automated (CI, synthetic 1 MiB image): unedited build is byte-identical; dry run
  writes nothing; applied builds carry the patches and a valid checksum; mismatched
  base, custom records, overwrite and size are refused (`tests/test_rom_build.py`).
- Local ROM: chest 26 (Link's house, `$120104`, source item byte `$12` "LAMP" per
  `Ancilla/ancilla_init.asm`) edited to `$47` ("300 RUPEES") built a ROM whose diff is
  exactly `$00E9BE 12→47` plus the checksum (`$AF0D→$AF42`). The stock image boots in
  snes9x 1.63. **Playtesting the built ROM is user-run**: the 2026-10-31 build is at
  `project/chest26-300-rupees.sfc` (git-ignored) — open the chest in Link's house; it
  should give 300 rupees instead of the lamp.
