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

**Source-name caveat:** the consumer refers to
`Text_DictionaryPointers`, while the visible data declaration is labelled
`DictionaryPointers`. The pinned source search shows these names in different
places but does not show an explicit alias declaration. Since the disassembly
README marks this source as work in progress and not buildable by itself, record
this mismatch and verify the intended symbol mapping before relying on it for
an automated extraction.

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
The audit preserves both values and does not inspect fragment payload bytes.
See the [text dictionary audit schema](./text-dictionary-audit.schema.json).


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
16-bit LoROM pointer candidates calculated from the registered
`text-dictionary-fragments` source offsets. It reports mismatched bytes and
retains the existing `.You` 2-byte-versus-6-byte source-extent warning
separately from pointer-byte results.

This is not a claim that the source-commented offsets are canonical: ROM
provenance and those candidate offsets remain unverified, fragment payload
bytes are not read, and no message text is decoded. The source also uses
`Text_DictionaryPointers` in the consumer while its visible declaration is
`DictionaryPointers`; this symbol-name mapping is still unresolved. A clean
comparison only shows that the bytes in the supplied file agree with the
source-derived candidates. See the
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
