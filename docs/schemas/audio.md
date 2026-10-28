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


## Music track pointer index

The first committed source inventory is
`data/extracted/music-track-index.json`. It records the 35 two-byte
expressions under `base SONG_POINTERS` in `SongBank_Underworld_Main` at
pinned revision `347c23f9fc019c72d32da537c9cb235f468d021d`.

- Table file offsets: `$0D8004–$0D8049` (35 entries, two bytes each).
- Source track indices: `$01–$23`; a separate zero-based `table_index` is
  provided for programmatic iteration.
- Fifteen entries are explicit `$0000` empty pointers.
- Four entries alias a previously named target: `$18` to `Song12_Cave`,
  `$21` to `Song1D_AgahnimEscapes`, `$22` to `Song1E_MeetingGanon`, and
  `$23` to `Song1F_KingOfThieves`.

Aliases and empty entries are retained as data. The inventory does not resolve
the symbolic expressions to SPC RAM addresses, assume indices map one-to-one
to payload labels, or read the referenced song chunks. The pinned source tree
has no tracked files under `bin/music/`, so this is a pointer-index export,
not a reproducible audio build or audio decoder.

Regenerate the index with:

```bash
uv run zelda-suite inspect-music-track-index \
  reference/AsarUSALTTPDisassembly/Bank1B.asm \
  --table-offset '$0D8004' \
  --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d \
  --output /tmp/music-track-index.json
uv run zelda-suite validate-source-export /tmp/music-track-index.json
diff -u data/extracted/music-track-index.json /tmp/music-track-index.json
```

The JSON schema for the export is
[`music-track-index.schema.json`](./music-track-index.schema.json). The named
asset loader exposes it as `load_extracted_asset("music-track-index")`.


## Music payload source inventory

`data/extracted/music-payload-inventory.json` contains the 15 labelled
`incbin` declarations for `bin/music/` in pinned `Bank1B.asm`. It is
separate from the `SONG_POINTERS` index because these declarations describe
payload storage ranges, not song-index relationships.

Twelve main-song declarations include explicit `Size:` annotations on their
`incbin` lines, and each matches its source-commented inclusive file range.
The three auxiliary declarations—`Song1D_AgahnimEscapes`,
`Song1F_KingOfThieves`, and `Song1E_MeetingGanon`—have source-commented
start/end offsets but no inline `Size:` annotation. Their recorded
`declared_size_bytes`, computed end, and source-range comparison remain null
instead of treating a calculated range length as a source-declared size.

Regenerate the file with the existing source-only inventory command:

```bash
uv run zelda-suite inspect-incbin \
  reference/AsarUSALTTPDisassembly/Bank1B.asm \
  --source-revision 347c23f9fc019c72d32da537c9cb235f468d021d \
  --output /tmp/music-payload-inventory.json
uv run zelda-suite validate-source-export /tmp/music-payload-inventory.json
diff -u data/extracted/music-payload-inventory.json /tmp/music-payload-inventory.json
```

The inventory does not open `bin/music/` files. Those payloads are absent from
the pinned submodule, and no audio bytes are included in the project.


## Pointer-index and payload-label cross-reference

The 35-slot `SONG_POINTERS` export contains 16 distinct non-empty target
symbols. Every one of the 15 labels in the committed `incbin` payload inventory
also appears in that pointer index, including the repeated targets for
`Song12_Cave`, `Song1D_AgahnimEscapes`, `Song1E_MeetingGanon`, and
`Song1F_KingOfThieves`.

One additional target symbol, `Song0B_FairyTheme`, is not a label in the
15-declaration `music-payload-inventory`. The source-only cross-reference test
records this exact set difference. It does **not** establish that the song is
absent, that its payload is missing from the ROM, or that the source expression
resolves to a particular file offset; the 15-row inventory only describes the
`incbin` declarations captured from this source block.

Recheck the relationship with:

```bash
uv run pytest tests/test_music_track_index.py
```

This is source-symbol consistency only. It does not read the untracked
`bin/music/*.bin` paths or validate any address against a local ROM.


## Cross-check pointer targets and payload declarations

Run `uv run zelda-suite audit-music-assets` to join the registered
`music-track-index` and `music-payload-inventory` exports. It preserves empty
pointer slots and aliases while reporting target labels that lack payload
declarations, payload declarations that are not referenced by the index, and
payload labels whose size is unknown.

The committed source-only baseline has 35 pointer entries: 15 empty slots, four
aliases, and 16 distinct non-empty target labels. All 15 declared payload labels
appear in the pointer target set, but `Song0B_FairyTheme` has no matching
declaration in the inventory. Three auxiliary payload declarations have source
ranges but no declared byte size: `Song1D_AgahnimEscapes`,
`Song1E_MeetingGanon`, and `Song1F_KingOfThieves`. Those are report findings,
not conclusions that payload bytes are absent from a clean local ROM.
The audit does not read audio payload bytes, resolve pointer values, or verify
offsets against a ROM. See the
[music audit schema](./music-asset-audit.schema.json).
