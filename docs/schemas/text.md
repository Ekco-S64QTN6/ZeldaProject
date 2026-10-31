# Message and dialogue data: source discovery

Status: **Phase 1 discovery, not a text decoder or final message schema.**
The pinned source labels message byte streams and documents the runtime pointer
workspace and dictionary-compressed tokens. A complete extractor still needs
the pointer-construction routine, token decoder, and a local clean US ROM for
verification.

## ROM-resident message blocks

The pinned
[`Bank1C.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Bank1C.asm)
declares the main stream as `Message_Data` over file offsets
`$0E0000–$0E7F29`. It labels individual messages such as `Message_0000`,
`Message_0001`, and `Message_0005` at their byte offsets; the first message
is a single `$7F` terminator byte. The source comments render human-readable
text fragments next to encoded bytes, which is useful for review but is not a
replacement for parsing the actual byte stream.

The pinned
[`Bank0E.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Bank0E.asm)
declares an additional block, `Message_DataExtra`, at
`$075F40–$076E21`. It begins with `Message_0167`, following the IDs in the
main message block. The ROM-analysis log also points to `$076E20` as more text
in this format; confirm the exact inclusive endpoint against the local ROM
before treating that annotation as a separate boundary.

These blocks are not a simple plain-text file. Message streams contain encoded
character bytes, dictionary-fragment tokens, line controls, and other
instructions. Examples visible in the source include `$75` for “Line 2”,
`$76` for “Line 3”, and `$7F` for “End of message”; `$7A` is commented as
“Set draw speed” and is followed by a parameter byte. Preserve the raw byte
sequence and offsets in the first extraction stage.

## Dictionary-fragment pointers

The source declares `DictionaryPointers` at file offsets
`$074703–$0747C6`. Its inclusive length is `0xC4` bytes, which is 98
two-byte pointer entries. Each listed word points to a named fragment such as
`DictionaryEntries_fourSpaces`, `DictionaryEntries_and_space`, or
`DictionaryEntries_and_no_space`.

The ROM log describes this region as dictionary-entry pointers that establish
a start point and an upper bound. The consumer in
[`Bank0E.asm`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Bank0E.asm)
indexes the pointer array, reads the current pointer and the following pointer,
then copies bytes up to that upper bound into the dialogue processing buffer.
Thus adjacent pointer values delimit variable-length dictionary fragments;
they should not be treated as fixed-size strings.

**Source-name caveat:** the consumer's two loads at
[`Bank0E.asm:6018–6019`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Bank0E.asm#L6018-L6019)
refer to `Text_DictionaryPointers+2` and `Text_DictionaryPointers+0`, while
the sole global table declaration in the pinned file is
[`DictionaryPointers:` at line 6039](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Bank0E.asm#L6039).
The two prefixed-name occurrences are the consumer accesses; no explicit
`Text_DictionaryPointers:` declaration or alias appears in the pinned file.
The disassembly README marks the source as work in progress and not buildable
by itself. Record the unresolved mapping; do not silently rename the table or
invent an alias. A separate test pins this source fact without claiming how an
external assembly/build process might resolve it.

## Runtime message-pointer workspace

The pinned
[`Logs/Zelda_3_RAM.log`](https://github.com/JaredBrian/AsarUSALTTPDisassembly/blob/347c23f9fc019c72d32da537c9cb235f468d021d/Logs/Zelda_3_RAM.log)
describes `$7F71C0` as the text/dialogue pointer array, with length `0x4A7`
bytes, and says each pointer is three bytes. The adjacent address
`$7F7667` begins free RAM. The size arithmetic is:

- `0x4A7 = 1,191` bytes
- `1,191 / 3 = 397` three-byte pointers
- `$7F71C0 + 0x4A7 = $7F7667`, matching the log's next address

This is a **WRAM workspace**. The source says the pointers are built
procedurally; it is not a ROM-resident pointer table that can be copied
verbatim from the base ROM. Preserve its role as a runtime index, separate from
the message byte streams and dictionary pointers.

## Suggested extraction layers

Keep these concerns distinct in the project model:

| Layer | Initial record contents | Do not assume yet |
| --- | --- | --- |
| Message stream | Message ID, source file/label, ROM file offset, raw encoded bytes, terminator status, source revision | Plain UTF-8 text or a complete character map |
| Dictionary fragment | Fragment index, pointer-table slot, start and upper-bound pointer values, raw fragment bytes | Fixed string length or one token per English word |
| Runtime message index | Message ID as established by the loader, constructed three-byte pointer, construction method/source location | That the WRAM pointer array is stored as-is in ROM |
| Decoder control token | Raw token byte, observed source comment/handler, interpretation status | Semantics inferred only from a text comment |

Message IDs are shown in the source comments, but the extraction routine should
preserve source ordering and exact offsets and then validate the message-pointer
construction logic before treating the ID range as a dense public API.

## Validation gates

1. Trace the routine that builds the `$7F71C0` pointer array and document how
   IDs map to the two ROM-resident message blocks.
2. Verify message stream starts/terminators against a local clean US ROM and
   add synthetic byte fixtures for empty, normal, multi-line, and malformed
   messages.
3. Trace the dictionary-token branch and confirm the start/upper-bound pointer
   semantics, including the `Text_DictionaryPointers` vs. `DictionaryPointers`
   name mismatch.
4. Inventory every control token used by the decoder before offering text-edit
   CRUD. Keep raw bytes and decoded display text side-by-side so the encoding
   round-trips without drift.
5. Keep ROM files and ROM-derived binary slices local; do not commit them.

This is documentation only. It does not read or write ROM bytes and does not
claim message extraction or text editing is implemented.


## Fragment extent metadata

The committed
[`text-dictionary-fragments.json`](../../data/extracted/text-dictionary-fragments.json)
inventory connects each pointer target to the corresponding local fragment
label and records source-comment offsets and directive widths without copying
the encoded fragment bytes. It also identifies an unresolved source mismatch
at `.You`: the next label begins two bytes after it, while the source directive
states three `dw` values (six bytes). See the
[extract inventory notes](../extracted-data.md) and
[export schema](./dictionary-inventory-export.schema.json).

This inventory is not a text decoder and is not an edit-ready text representation.

## Source message index

The committed `data/extracted/text-message-index.json` contains a metadata-only
index of 397 message labels from the main and extra message blocks. It records
the line for each `Message_####` label, any immediately preceding standalone
source offset annotation, the source-derived sequential offset, and byte count
computed from the Asar directives.

The main block's declared bytes match its header range, but six offset comments
do not agree with sequential sizes (three annotations are malformed). The extra
block has no per-message offset comments and its declared bytes are one byte
short of its header range. These discrepancies are explicitly recorded. The
index does not include encoded bytes or decoded text and does not validate the
runtime message-pointer construction.


## Cross-check the committed dictionary exports

Run `uv run zelda-suite audit-text-dictionary` to join the registered
`text-dictionary-pointers` and `text-dictionary-fragments` exports without
reading a ROM. The audit checks source provenance, pointer/fragment labels,
indexes and entry offsets, plus the adjacency of each fragment's next offset
and the following record's start offset. When source extents are present, it
also checks that each extent equals the difference between those two offsets.
These checks validate internal metadata relationships only; they do not verify
source offsets against ROM bytes or resolve symbolic pointers.

The existing `.You` source extent discrepancy remains a warning: the next
source offset implies a 2-byte extent, while the directive declares 6 bytes.
The runtime consumer uses the next pointer as an exclusive bound, so those
source comments imply a two-byte read interval even though `dw $18, $28, $2E`
declares six bytes. This source-only audit preserves both values, does not
inspect fragment payload bytes, and does not decide which source annotation or
directive should change. See the
[text dictionary audit schema](./text-dictionary-audit.schema.json).


## Audit known message-index discrepancies

Run `uv run zelda-suite audit-text-message-index` to summarize the source
offset and block-size diagnostics from the committed index without requiring
the disassembly submodule. The report separates malformed source annotations
from valid annotations that disagree with sequential offsets, counts messages
with no annotation, and records block declared-size differences. All are
warnings about source metadata, not verified ROM offsets or decoded text.

The pinned baseline currently contains 397 messages across two source blocks:
six offset annotations disagree with sequential offsets (three are malformed),
38 messages in `Message_DataExtra` lack individual offset annotations, and the
extra block's declared message bytes total is one byte smaller than its header
range. The audit preserves these discrepancies. See the
[text-message index audit schema](./text-message-index-audit.schema.json).


## Read-only dictionary pointer word verification

With a local 1 MiB headerless ROM file available, run
`uv run zelda-suite verify-text-dictionary-pointers PATH_TO_ROM`. The
verifier compares the 98 two-byte words at file offset `$074703` against
16-bit LoROM candidates. Ordinary targets use the registered fragment's
source-commented start offset. The terminal `DictionaryEntries_endOfTable`
target uses the exclusive end after the pinned inclusive data range
`$0747C7-$0748D8 DATA` (file offset `$0748D9`), because the runtime consumes
each token until the next pointer. Report v2 preserves the original terminal
comment offset and labels which offset rule produced each candidate.

The `.You` 2-byte-versus-6-byte source-extent warning remains separate from
pointer-byte results. The consumer reads its start and exclusive end from
adjacent pointer entries, but the pinned `.You` directive declares six bytes
inside a two-byte comment-derived interval. The terminal candidate at
`$C8D9` follows the inclusive DATA-range endpoint, not a rewrite of the raw
`.endOfTable` comment at `$0748D8`. This is not a claim that the source
annotations are canonical: ROM provenance and fragment bytes remain
unverified, and no text is decoded. The consumer uses
`Text_DictionaryPointers` while the visible declaration is
`DictionaryPointers`; the pinned file has no explicit alias, so this
symbol-name mapping remains unresolved. A clean comparison only shows that
bytes in the supplied file agree with the candidate rules. See the
[text dictionary pointer verification schema](./text-dictionary-pointer-verification.schema.json)
and [real-ROM runbook](../real-rom-verification.md).


## Read-only encoded message byte verification

Run `uv run zelda-suite verify-text-message-bytes PATH_TO_ROM` with two
`--block` options to compare literal `db $XX` bytes from the pinned
`Message_Data` and `Message_DataExtra` source regions to a local image.
The command uses sequential offsets derived from the number of literal bytes
in each message. It reports byte-level mismatches with message IDs and offsets,
plus existing source offset-annotation and block-size discrepancies.

The parser deliberately accepts only literal one-byte hexadecimal `db`
values inside each bounded block; it fails closed on expressions instead of
evaluating assembler syntax. The command reads a local ROM but does not decode
message text, dictionary-compression tokens, or semantic control codes.
Source-declared block ranges and ROM provenance are not independently
verified by the command. A synthetic test or a matching byte report does not
establish that the candidate source ranges are canonical. See the
[text-message byte verification schema](./text-message-byte-verification.schema.json)
and [real-ROM runbook](../real-rom-verification.md).

## Decoding messages

`uv run zelda-suite decode-text-messages [--rom PATH] [--message-id N] [--text] [--output PATH]`
(`zelda_suite.extract.text_decode`) decodes all 397 messages into readable text and a
lossless markup. Format `zelda-suite-text-messages`, version 1.

**Grammar** — from the pinned consumer, `Text_LoadCharacterBuffer` / `Text_Command` /
`Text_DictionarySequence` (Bank0E.asm): a byte below `$67` is a glyph; `$67–$7F` is a
command (`$6B–$6E` and `$77–$7A` take one parameter byte; `$7F` ends the message); `$88`
and up is dictionary entry `byte − $88`, copied from pointer *i* up to pointer *i + 1*.

**Glyphs** — derived from the source's own annotations: 5,044 annotated `db` lines of
the two message blocks aligned byte-for-byte; every glyph maps to a single character
(`$25` reads "L" once against 1,211 "l", a typo; `tests/test_text_decode.py` re-derives
the map from the pinned source). `X`, `4`, `6`, `7`, `9` (`$17 $38 $3A $3B $3D`) never
appear in an annotated line and are **inferred** from alphabet/digit order; each message
lists any inferred or unknown glyphs it uses (`$4A` and `$4B` appear once each, unknown,
written `{glyph 4A}`). The seven heart-piece glyphs `$52–$58` share "♥" and are written
`{glyph XX}` in markup.

**Markup** — glyphs as characters; dictionary entries as `[text]` (the 97 entry texts
are distinct); commands as `{Name}` / `{Name XX}` with the consumer's names
(`{Speed 00}`, `{Line2}`, `{Name}`, `{WaitKey}` …); the final `{End}` is implied.
`encode_markup(decode_markup(b)) == b` for every message, from the source and from the
ROM. `text` is the readable rendering: dictionary expanded, `Line2`/`Line3`/`Scroll` as
line breaks, the player's name as `<Name>`.

**The `$80` block marker** — `Message_0166`, the main block's last message, is followed by
`db $80 ; Change banks`, which the source index counts with that message. The decoder
reports it as `trailing_block_marker` and decodes the message up to its End.

**`.You`, resolved by the ROM** — the source declares dictionary entry `$60` as
`dw $18, $28, $2E` beside a two-byte offset interval. Decoded from source alone it stays
unresolved (`{dict 60}` in 127 messages). With `--rom`, the dictionary is read through
the ROM's pointer table as the game reads it: on the fingerprint-matched US image (2026-10-31)
entry `$60` is the three bytes `18 28 2E` ("You") at `$0748D6`, ending at the table's
terminal pointer `$C8D9` (`$0748D9`). The `dw` is a declaration error in the source (the
bytes are `db` values); the terminal pointer is the exclusive end. With the ROM, all 397
messages decode with no unresolved entries, and each message's ROM bytes are required to
equal the source literals before decoding.
