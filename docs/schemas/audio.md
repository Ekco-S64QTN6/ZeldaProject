# Music payload layout: source discovery

Status: **Phase 1 discovery; not an audio decoder or complete soundtrack schema.**
The pinned Asar source provides useful file-range comments, song labels, and
`incbin` paths, but the binary song payloads are absent from the submodule's
tracked tree.

## Bank 1B overview

The pinned
[`Bank1B.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Bank1B.asm)
declares `SongBank_Underworld_Main` over file offsets `$0D8000–$0DACC2` and
`SongBank_Underworld_Auxiliary` over `$0DACC3–$0DB1D2`. It begins each block
with transfer metadata and labels a song-index table under `base SONG_POINTERS`.
That table contains empty values and aliases (for example, index `$18` refers
to `Song12_Cave`, and the later indices `$21–$23` refer to songs already named
elsewhere). Do not infer a one-to-one sequential relationship between song
index, song label, and file location.

The source comments distinguish ROM file offsets (such as `$0D804A`) from SPC
RAM addresses (such as `$D046`). They describe different address spaces; keep
them as separately named fields in an inventory rather than using either as a
substitute for the other.

## Main music payloads

The `incbin` declarations in `Bank1B.asm` record the following source ranges
and sizes. The file ranges are inclusive, and the sizes below agree with the
commented endpoints.

| Source label | Headerless file offsets | Declared size | Include path |
| --- | --- | ---: | --- |
| `Song10_HyruleCastle` | `$0D804A–$0D8BEF` | `0x0BA6` | `bin/music/song10.bin` |
| `Song11_PendantDungeon` | `$0D8BF0–$0D913D` | `0x054E` | `bin/music/song11.bin` |
| `Song12_Cave` | `$0D913E–$0D9434` | `0x02F7` | `bin/music/song12.bin` |
| `Song13_Fanfare` | `$0D9435–$0D96FC` | `0x02C8` | `bin/music/song13.bin` |
| `Song14_Sanctuary` | `$0D96FD–$0D9921` | `0x0225` | `bin/music/song14.bin` |
| `Song15_Boss` | `$0D9922–$0D9C0E` | `0x02ED` | `bin/music/song15.bin` |
| `Song16_CrystalDungeon` | `$0D9C0F–$0DA1D4` | `0x05C6` | `bin/music/song16.bin` |
| `Song17_Shop` | `$0DA1D5–$0DA307` | `0x0133` | `bin/music/song17.bin` |
| `Song19_ZeldaRescue` | `$0DA308–$0DA583` | `0x027C` | `bin/music/song19.bin` |
| `Song1A_CrystalMaiden` | `$0DA584–$0DA90C` | `0x0389` | `bin/music/song1A.bin` |
| `Song1B_BigFairy` | `$0DA90D–$0DAB6D` | `0x0261` | `bin/music/song1B.bin` |
| `Song1C_Suspense` | `$0DAB6E–$0DACC2` | `0x0155` | `bin/music/song1C.bin` |

## Auxiliary music payloads

The same source places these files in `SongBank_Underworld_Auxiliary`:

| Source label | Headerless file offsets | Declared size | Include path |
| --- | --- | ---: | --- |
| `Song1D_AgahnimEscapes` | `$0DACC7–$0DAD79` | `0x00B3` | `bin/music/song1D.bin` |
| `Song1F_KingOfThieves` | `$0DAD7A–$0DB11F` | `0x03A6` | `bin/music/song1F.bin` |
| `Song1E_MeetingGanon` | `$0DB120–$0DB1D2` | `0x00B3` | `bin/music/song1E.bin` |

The auxiliary block starts with four bytes of transfer metadata at
`$0DACC3–$0DACC6`, before the first included song chunk at `$0DACC7`.

## Payload availability

At the pinned submodule revision
`347c23f9fc019c72d32da537c9cb235f468d021d`, the recursive Git tree contains
zero files under `bin/music/`. The source includes refer to these paths, but
the binary chunks are not available as tracked build inputs in that snapshot.
The inventory is useful for future local-ROM validation, but it does not
constitute a reproducible audio build today.

## Recommended raw inventory fields

- `source_label`: exact Asar label such as `Song10_HyruleCastle`.
- `source_file_offset_start` / `source_file_offset_end`: source-commented
  inclusive ROM offsets.
- `declared_size_bytes`: size annotation from the `incbin` declaration.
- `incbin_path`: exact path expression from the source.
- `song_index_expressions`: exact `dw` expressions and index comments, kept
  separate from the included payload metadata.
- `spc_address_range`: optional source-commented SPC RAM address range, never
  conflated with ROM file offsets.
- `source_revision` and `payload_available`: audit trace and local availability
  state.

## Validation gates

1. Inventory pointer-table expressions and included payloads separately; retain
   aliases and unused/zero pointer values from the table.
2. Verify the range/size arithmetic against the source comments, then compare
   source offsets with a locally supplied clean US ROM.
3. Trace how the SPC pointer values and transfer header are consumed before
   designing an editable music model.
4. Keep any local ROM or extracted binary chunks out of Git. Use synthetic
   metadata fixtures for parser tests and locally supplied files for byte
   verification.

This note documents source declarations only; it neither reads nor modifies ROM
bytes or audio payloads.
