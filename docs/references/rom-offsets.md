# Canonical ALttP ROM offset map

This map is for the clean, headerless US base ROM specified by
[`CLAUDE.md`](../../CLAUDE.md). It describes the canonical LoROM banks used by
the pinned reference disassembly; it is a navigation aid, not permission to
write bytes directly. ROM reads and writes still belong in the future
`extract/` and `write/` modules.

## Mapping rule

The pinned [`Zelda3.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Zelda3.asm#L33-L55)
declares `lorom` and assembles each bank into its `$BB:8000` window. For the
canonical banks `$00`–`$1F`, CPU addresses in `$8000`–`$FFFF` map to file
offsets as follows:

```text
file_offset = bank * 0x8000 + (cpu_address - 0x8000)
```

The offset assumes the file starts at ROM byte zero (no 512-byte copier
header). For example, `$00:8000` maps to file offset `0x000000`,
`$01:8000` maps to `0x008000`, and `$1F:8000` maps to `0x0F8000`.
This aligns with the `org $008000` declaration and offset comments in
[`Bank00.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Bank00.asm#L3-L16),
[`Bank01.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Bank01.asm#L3-L12),
and the final `$0F8000`–`$0FFFFF` range in
[`Bank1F.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Bank1F.asm#L3-L8).

## Bank table

Each canonical LoROM bank contributes one 32 KiB slice (0x8000 bytes) to the
1 MiB headerless file. The CPU window shown is the bank's ROM-mapped half.

| Disassembly bank | CPU address window | Headerless file offsets |
| --- | --- | --- |
| `Bank00.asm` | `$00:8000–$00:FFFF` | `$000000–$007FFF` |
| `Bank01.asm` | `$01:8000–$01:FFFF` | `$008000–$00FFFF` |
| `Bank02.asm` | `$02:8000–$02:FFFF` | `$010000–$017FFF` |
| `Bank03.asm` | `$03:8000–$03:FFFF` | `$018000–$01FFFF` |
| `Bank04.asm` | `$04:8000–$04:FFFF` | `$020000–$027FFF` |
| `Bank05.asm` | `$05:8000–$05:FFFF` | `$028000–$02FFFF` |
| `Bank06.asm` | `$06:8000–$06:FFFF` | `$030000–$037FFF` |
| `Bank07.asm` | `$07:8000–$07:FFFF` | `$038000–$03FFFF` |
| `Bank08.asm` | `$08:8000–$08:FFFF` | `$040000–$047FFF` |
| `Bank09.asm` | `$09:8000–$09:FFFF` | `$048000–$04FFFF` |
| `Bank0A.asm` | `$0A:8000–$0A:FFFF` | `$050000–$057FFF` |
| `Bank0B.asm` | `$0B:8000–$0B:FFFF` | `$058000–$05FFFF` |
| `Bank0C.asm` | `$0C:8000–$0C:FFFF` | `$060000–$067FFF` |
| `Bank0D.asm` | `$0D:8000–$0D:FFFF` | `$068000–$06FFFF` |
| `Bank0E.asm` | `$0E:8000–$0E:FFFF` | `$070000–$077FFF` |
| `Bank0F.asm` | `$0F:8000–$0F:FFFF` | `$078000–$07FFFF` |
| `Bank10.asm` | `$10:8000–$10:FFFF` | `$080000–$087FFF` |
| `Bank11.asm` | `$11:8000–$11:FFFF` | `$088000–$08FFFF` |
| `Bank12.asm` | `$12:8000–$12:FFFF` | `$090000–$097FFF` |
| `Bank13.asm` | `$13:8000–$13:FFFF` | `$098000–$09FFFF` |
| `Bank14.asm` | `$14:8000–$14:FFFF` | `$0A0000–$0A7FFF` |
| `Bank15.asm` | `$15:8000–$15:FFFF` | `$0A8000–$0AFFFF` |
| `Bank16.asm` | `$16:8000–$16:FFFF` | `$0B0000–$0B7FFF` |
| `Bank17.asm` | `$17:8000–$17:FFFF` | `$0B8000–$0BFFFF` |
| `Bank18.asm` | `$18:8000–$18:FFFF` | `$0C0000–$0C7FFF` |
| `Bank19.asm` | `$19:8000–$19:FFFF` | `$0C8000–$0CFFFF` |
| `Bank1A.asm` | `$1A:8000–$1A:FFFF` | `$0D0000–$0D7FFF` |
| `Bank1B.asm` | `$1B:8000–$1B:FFFF` | `$0D8000–$0DFFFF` |
| `Bank1C.asm` | `$1C:8000–$1C:FFFF` | `$0E0000–$0E7FFF` |
| `Bank1D.asm` | `$1D:8000–$1D:FFFF` | `$0E8000–$0EFFFF` |
| `Bank1E.asm` | `$1E:8000–$1E:FFFF` | `$0F0000–$0F7FFF` |
| `Bank1F.asm` | `$1F:8000–$1F:FFFF` | `$0F8000–$0FFFFF` |

## Guardrails

- The map assumes the exact 1,048,576-byte, headerless US ROM. Do not silently
  add or subtract `0x200`; reject or normalize copier-headered input before
  extraction.
- Not every SNES CPU address is a ROM address. This formula applies only to
  the high-half ROM window for the canonical banks listed above; it must not
  be applied to WRAM, hardware registers, or arbitrary mirrored addresses.
- Before any future byte write, cite both the project-data row being changed
  and the relevant pinned disassembly label/address. Produce a deterministic
  diff and pass the project's planned emulator smoke test.
