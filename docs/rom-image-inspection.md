# Read-only ROM image inspection

Use `zelda-suite inspect-rom PATH` to record a ROM file's size, SHA-256, a
size-based header assessment, and the canonical LoROM file-offset mapping.

```bash
uv run zelda-suite inspect-rom \
  "base_game_roms/Legend of Zelda, The - A Link to the Past (U) [!].smc" \
  --output /tmp/base-rom-inspection.json
```

The command is read-only. It opens the selected ROM only inside
`zelda_suite.extract.rom_image`, hashes it, and produces JSON metadata; it
does not modify or copy the image and should not be used with the output path
pointing at the ROM itself.

## Header-state assessment

The expected US image size is 1 MiB (1,048,576 bytes). That size is consistent
with a headerless image but does not prove that the dump is the correct US
release. An image whose size is 512 bytes greater than the expected image, or
has a 512-byte remainder relative to the 32 KiB LoROM bank size, is reported as
`copier-header-suspected-by-size`. Other sizes are reported as
`unrecognized-size`. The tool does not remove a header or attempt to detect
one by changing bytes.

## LoROM file offsets

For a headerless image, the helper maps each file offset to the canonical
low-bank CPU address used by the disassembly:

`bank = file_offset // 0x8000`
`address = 0x8000 + (file_offset % 0x8000)`

For example, file offset `$058000` maps to `$0B8000`. This is the linear,
low-bank notation used for source `org` declarations; mirrored SNES bank
aliases are not emitted. The map is marked inapplicable when the image size
does not match the expected headerless image.

## Interpretation

Treat the SHA-256 as an identity fingerprint for the local file, not as a
claim by itself that the contents match a known-good canonical dump. The user's
2026-10-29 local image matched the documented No-Intro USA size/CRC-32/SHA-1/MD5
fingerprint, and a read-only YAZE v0.7.2 smoke test successfully read several
ROM, dungeon, graphics/palette, and message views. The overworld screen-80 read
still fails with an out-of-range offset, and one staircase label was malformed;
this is partial capability evidence, not a completed editor integration gate.
See [`real-rom-verification.md`](./real-rom-verification.md) for the exact hash,
commands, and limitations. ROMs and ROM-derived bytes remain local and must not
be committed.
