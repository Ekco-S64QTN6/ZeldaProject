# Local ROM verification runbook

This runbook checks the current read-only ROM tooling against an authorized,
locally supplied US ROM. It separates file diagnostics from actual byte
comparisons and external-tool smoke tests. It never writes, patches, normalizes,
or redistributes a ROM.

Run from the repository root in a POSIX shell. Keep the ROM in the gitignored
`base_game_roms/` directory. Never commit ROM images, partial slices, or
ROM-derived binary fixtures.

The `ROM` shell variable used by later commands must be set in the same
terminal session. If you open a new terminal, repeat the assignment in step 1
before running a snippet that passes `"$ROM"` to Python.

## 1. Confirm the local input

```bash
uv sync --extra dev
ROM='base_game_roms/Legend of Zelda, The - A Link to the Past (U) [!].smc'
test -r "$ROM" && echo "ROM is readable" || echo "ROM missing or unreadable"
stat -c '%n: %s bytes' "$ROM"
sha256sum "$ROM"
```

On macOS, use `stat -f '%N: %z bytes' "$ROM"` if `stat -c` is unavailable.
The SHA-256 is an identity fingerprint; the repository does not bundle a
trusted canonical-dump hash.

## 2. Inspect the image and environment

```bash
uv run zelda-suite inspect-rom "$ROM"
uv run zelda-suite doctor
```

`inspect-rom` reports size, SHA-256, a size-based header assessment, and
LoROM offset mapping. A 1,048,576-byte file is consistent with a headerless
1 MiB image, but size does not prove authenticity. A 1,049,088-byte image
suggests a 512-byte copier header; do not remove it automatically.

`doctor` checks the canonical path and whether `z3ed` and `z3cli` are on
`PATH`; it does not invoke either tool or prove ROM compatibility. Missing or
incorrect ROM size causes exit status 1; missing tools are warnings.

## 3. Self-diff smoke test

Use a fresh temporary output path because the CLI refuses to overwrite files.

```bash
TEST_DIR="$(mktemp -d)"
printf 'Test reports: %s\n' "$TEST_DIR"
uv run zelda-suite diff-rom "$ROM" "$ROM" --output "$TEST_DIR/self-diff.json"
python - "$TEST_DIR/self-diff.json" <<'PY'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
diff = report["diff"]
print("Base/modified hashes match:",
      report["base_rom"]["sha256"] == report["modified_rom"]["sha256"])
print("Changed bytes:", diff["changed_byte_count"])
print("Changed regions:", diff["region_count"])
PY
```

Expected: hashes match, changed bytes are zero, and changed regions are zero.
This confirms the file-reading/diff/report path only; it does not test semantic
extraction or whether a ROM boots.

## 4. Compare source-annotated table values with local bytes

The script below cross-checks the five falling-prize source tables at their
currently documented offsets. It reads the local ROM into memory for these
comparisons and reports matches/mismatches. It does not write any bytes or
create ROM slices.

```bash
python - "$ROM" <<'PY'
from pathlib import Path
import sys

if len(sys.argv) != 2:
    print("STOP: pass the ROM path as the first argument.", file=sys.stderr)
    raise SystemExit(2)

rom_path = Path(sys.argv[1])
if not rom_path.is_file():
    print(f"STOP: ROM path is not a file: {rom_path}", file=sys.stderr)
    print("Set ROM in this same shell and rerun the command.", file=sys.stderr)
    raise SystemExit(2)

try:
    rom = rom_path.read_bytes()
except OSError as exc:
    print(f"STOP: could not read ROM path {rom_path}: {exc}", file=sys.stderr)
    raise SystemExit(2)

EXPECTED_SIZE = 1_048_576
if len(rom) != EXPECTED_SIZE:
    print(f"STOP: expected a 1 MiB ROM, got {len(rom):,} bytes")
    print("Run inspect-rom first; do not adjust the file automatically.")
    raise SystemExit(2)

def words_le(values: list[int]) -> bytes:
    return b"".join(value.to_bytes(2, "little") for value in values)

tables = [
    ("item values", 0x048B90,
     bytes([0x10, 0x37, 0x39, 0x38, 0x26, 0x0F, 0x20])),
    ("fall heights", 0x048B97,
     bytes([0x60, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80])),
    ("Y offsets", 0x048B9E,
     words_le([0x0048, 0x0078, 0x0078, 0x0078,
               0x0078, 0x0068, 0x0078])),
    ("X offsets", 0x048BAC,
     words_le([0x0078, 0x0078, 0x0078, 0x0078,
               0x0078, 0x0080, 0x0078])),
    ("delay timers", 0x048BBA,
     bytes([0x40, 0x00, 0x00, 0x00, 0x00, 0xFF, 0x00])),
]

failures = 0
print(f"Read-only checks on: {rom_path.name}")
for name, offset, expected in tables:
    actual = rom[offset:offset + len(expected)]
    if actual == expected:
        print(f"PASS  {name}: offset 0x{offset:06X}, {len(expected)} bytes")
        continue

    failures += 1
    print(f"FAIL  {name}: offset 0x{offset:06X}")
    print(f"      expected: {expected.hex(' ').upper()}")
    print(f"      actual:   {actual.hex(' ').upper()}")
    for i, (want, got) in enumerate(zip(expected, actual)):
        if want != got:
            print(f"      first mismatch at 0x{offset + i:06X}: "
                  f"expected {want:02X}, got {got:02X}")
            break

print(f"\nResult: {len(tables) - failures}/{len(tables)} tables matched")
raise SystemExit(1 if failures else 0)
PY
```

A match means that table's source-declared values agree with the bytes at the
specified offsets in this file. It does not establish the file's provenance or
verify other source annotations. A mismatch must be investigated; do not
auto-correct source comments or shift offsets speculatively. Record the size,
SHA-256, table name, and mismatch offsets in the local test notes.

## 5. Cross-check registered scalar-table literals against the ROM

The repeatable `verify-rom-tables` command compares direct numeric values in
registered `zelda-suite-data-table` exports against the local ROM. It uses
each entry's declared file offset, the `db`/`dw`/`dl` directive width for
the literal bytes, and the export's entry stride for indexing. Simple negative
decimal literals (such as `db -5`) are checked as two's-complement values
within the signed range of that directive; symbolic or otherwise unresolved
expressions are skipped rather than guessed. The source exports are not
rewritten or normalized by this check.

Run from the repository root:

```bash
uv run zelda-suite verify-rom-tables "$ROM"
```

The command emits a JSON report with the ROM filename, size and SHA-256, a
per-table status, entry counts, and any mismatch offsets. The SHA-256 is a local
file fingerprint, not proof of provenance. By default, the report remains format
version 1 and unresolved expressions are counted as skipped.

For a diagnostic inventory of every skipped expression, add
`--include-skipped-expressions`:

```bash
uv run zelda-suite verify-rom-tables "$ROM" --include-skipped-expressions
```

This opt-in mode emits report format version 2. Each asset lists the original
expression, table index, source line, file offset, and a conservative syntax
classification (`symbol`, `symbol_with_numeric_addend`,
`compound_or_assembler_specific`, or `other`). These labels describe only syntax
shape; they do not resolve symbols, infer values, or execute assembler syntax.
See [`schemas/rom-table-verification-v2.schema.json`](./schemas/rom-table-verification-v2.schema.json).

Status values mean:
- `pass`: all entries were numeric and all compared bytes matched.
- `partial`: all compared bytes matched, but one or more entries were skipped.
- `skip`: no numeric entries were available for comparison.
- `fail`: at least one compared value mismatched, exceeded its directive width,
  or referred outside the image.

A nonzero exit status means at least one mismatch was found. The report is
still emitted, so it can be saved for investigation. To save it to a new file:

```bash
TEST_DIR="${TEST_DIR:-$(mktemp -d)}"
uv run zelda-suite verify-rom-tables "$ROM" \
  --output "$TEST_DIR/scalar-table-verification.json"
printf 'Verification report: %s\n' "$TEST_DIR/scalar-table-verification.json"
```

The command is read-only and never writes ROM bytes. It verifies only direct
numeric source-table literals plus simple negative decimal literals at their
recorded offsets; it does not decode semantics, validate skipped expressions,
or establish canonical ROM identity.
Review mismatches instead of shifting offsets or normalizing expressions
speculatively.

## 6. Verify overworld hidden-item pointers and sentinel-delimited lists

Before reading any ROM, you can inspect the source-derived layout only:

```bash
uv run zelda-suite inspect-overworld-hidden-items \
  --output /tmp/overworld-hidden-item-source-layout.json
```

This reports the declarations and computed offsets from the pinned disassembly; it is not a ROM check. The output schema is [`overworld-hidden-item-source-layout.schema.json`](./schemas/overworld-hidden-item-source-layout.schema.json).

Before comparing bytes, capture the source-consumer interpretation of each record's third byte:

```bash
TEST_DIR="${TEST_DIR:-$(mktemp -d)}"
uv run zelda-suite audit-overworld-hidden-item-value-semantics \
  --output "$TEST_DIR/hidden-item-value-semantics.json"
printf 'Source-consumer report: %s\n' "$TEST_DIR/hidden-item-value-semantics.json"
```

At the pinned source revision this report classifies 325 ordinary secret-state-mask
values and 26 extended selectors; the selector low nibble is used as a byte offset
into the four-word `Overworld_SecretTileType` table. It calls out `$84`'s special
branch. This is source-only evidence and reads no ROM; it does not establish that
the third bytes or replacement words match your file or resolve canonical item IDs.
Continue with the byte-comparison command below only when an authorized local ROM
is available.

The read-only `verify-overworld-hidden-items` command parses the pinned
`Bank1B.asm` declaration region and compares it with your local ROM. It
calculates the screen-label file offsets from source declaration widths,
converts those offsets to same-bank LoROM pointer words, and compares the
pointer table plus every declared record, sentinel, and replacement Map16 word.

```bash
TEST_DIR="${TEST_DIR:-$(mktemp -d)}"
uv run zelda-suite verify-overworld-hidden-items "$ROM" \
  --output "$TEST_DIR/hidden-item-verification.json"
printf 'Hidden-item report: %s\n' "$TEST_DIR/hidden-item-verification.json"
```

The report includes 128 pointer comparisons, 351 three-byte record comparisons,
67 two-byte sentinel comparisons, and four replacement-word comparisons (550
comparisons total when all are in bounds). It also derives the 128 area lists
using the runtime rule—advance three bytes and stop at a leading `$FFFF`
word—not at a source-label boundary. Shared pointers and zero-record lists are
preserved.

A nonzero exit status means at least one comparison mismatched; the JSON report
is still written for diagnosis. The test checks source-commented offsets
against this file; it does not prove that the image is a canonical dump or that
the declared offsets are correct for every ROM revision. Do not shift offsets
or alter source declarations to silence a mismatch. The command never writes
ROM bytes and does not decode the semantic meaning of item values or Map16
coordinates.

## 7. Verify the dungeon-room long-pointer table

The read-only `verify-dungeon-room-pointers` command compares the 320
three-byte entries at source-commented file offset `$0F8000` with candidate
target addresses derived from the three registered room-payload inventories.
Within each inventory, it anchors the source-order layout at the first
source-commented start offset and advances by each declaration's positive
source-declared payload size. It reports any later source-commented offsets that
disagree with that computed layout; comments are preserved and never rewritten.
The format-version-2 report schema is
[`dungeon-room-pointer-verification.schema.json`](./schemas/dungeon-room-pointer-verification.schema.json).

```bash
TEST_DIR="${TEST_DIR:-$(mktemp -d)}"
uv run zelda-suite verify-dungeon-room-pointers "$ROM" \
  --output "$TEST_DIR/dungeon-room-pointer-verification.json"
printf 'Dungeon-room pointer report: %s\n' "$TEST_DIR/dungeon-room-pointer-verification.json"
```

The report checks all 320 entries, identifies the 263 distinct target labels,
keeps the 39 explicit `RoomDataTiles_Empty` entries visible, and lists the
source-offset candidate and pointer indices for each of the 266 payload labels.
The three labels not referenced by the pointer table are included with an empty
index list.

A nonzero exit status means pointer bytes mismatch the sequential
payload-layout candidate; the JSON report is still written. The report keeps
both the source-commented and computed offsets for each target and includes
`source_offset_findings` for missing or conflicting comments. For the pinned
source snapshot, six comments currently disagree with the sequential layout:
`RoomDataTiles_00E1`, `RoomDataTiles_0011`, `RoomDataTiles_0050`,
`RoomDataTiles_00F9`, `RoomDataTiles_011C`, and `RoomDataTiles_0015`.
This is source-annotation evidence, not proof of ROM provenance. Re-run the
command against your authorized local image after updating the repository and
inspect both the byte-mismatch and source-offset-finding lists. This operation
does not check room payload bytes, identify playable rooms, or resolve the
296-versus-320 room count discrepancy. Do not rewrite comments to force a pass.
The command never writes ROM bytes.

## 8. Run the ROM-independent regression suite

```bash
uv run pytest -q
uv run ruff check src tests
uv run mypy src
```

These cover existing parsers, source exports, project store/migration,
inspection, diff, and CLI behavior. They are not substitutes for testing
YAZE/z3ed on your ROM.

## 9. Install and inspect external-tool capabilities

These tools are not needed for steps 1–6, but they are needed to attempt the
remaining Phase 0 integration gates.

- **YAZE / `z3ed`:** `z3ed` is YAZE's ROM inspection/editing CLI. The official
  [YAZE v0.7.2 release](https://github.com/scawful/yaze/releases/tag/v0.7.2)
  provides a generic Linux `.tar.gz` for distributions such as Arch Linux.
  Download and verify the official archive first:

  ```bash
  cd /tmp
  curl -fL -o yaze-0.7.2-Linux.tar.gz \
    https://github.com/scawful/yaze/releases/download/v0.7.2/yaze-0.7.2-Linux.tar.gz
  printf '%s  %s\n' \
    'b7310862e4306830f5631e81a030df4ff976106d9001d9e21c314bb5ad3dc8db' \
    'yaze-0.7.2-Linux.tar.gz' | sha256sum -c -

  tar -tzf yaze-0.7.2-Linux.tar.gz | head -80
  mkdir -p "$HOME/.local/opt/yaze-0.7.2"
  tar -xzf yaze-0.7.2-Linux.tar.gz -C "$HOME/.local/opt/yaze-0.7.2"
  find "$HOME/.local/opt/yaze-0.7.2" -type f \( -name z3ed -o -name yaze \) -print
  ```

  Inspect the archive listing and the paths printed by `find`; then invoke the
  discovered `z3ed` executable or wrapper with `--help` before adding any
  symlink to `~/.local/bin`. Do not use the Debian `.deb` package on Arch.
  The release does not bundle a ROM. If the prebuilt archive cannot run on
  your host, use YAZE's [official build guide](https://github.com/scawful/yaze/blob/master/docs/public/build/quick-reference.md)
  and its Linux `lin-rel` preset; build only the `z3ed` target and its required
  runtime assets rather than starting with the AI-enabled preset.
- **`z3cli`:** This is a separate, experimental agent harness, not part of
  YAZE or this Python package. Its [source repository](https://github.com/scawful/z3cli)
  documents a source install rather than a tagged release. Keep it in its own
  checkout and virtual environment, not in this project's `.venv`:

  ```bash
  mkdir -p "$HOME/src/tools"
  git clone https://github.com/scawful/z3cli.git "$HOME/src/tools/z3cli"
  cd "$HOME/src/tools/z3cli"
  python3 -m venv .venv
  . .venv/bin/activate
  python -m pip install -e .
  ```

  Installation alone does not configure a model endpoint or prove that its MCP
  tools work with this project. Keep that integration gate open until a real,
  reviewed tool call succeeds.

After installing whichever tool you are testing, inspect its capabilities
before invoking it. Do not run write, patch, rebuild, or save commands as part
of this diagnostic pass.

```bash
for tool in z3ed z3cli; do
  if command -v "$tool" >/dev/null 2>&1; then
    printf '\n=== %s: %s ===\n' "$tool" "$(command -v "$tool")"
    "$tool" --help
  else
    printf '\n=== %s: not installed/on PATH ===\n' "$tool"
  fi
done
```

Save the version/help output. The current doctor only checks PATH visibility,
and the repository does not yet define a tested, version-independent command
for a real YAZE/z3ed read. Confirm the installed tool's supported read-only
arguments before attempting an actual read.

## Text dictionary pointer words

After checking ROM size/provenance diagnostics, the read-only command below
compares the 98 two-byte dictionary pointer words in a local image with
source-derived candidates. Ordinary fragments use their source-commented
starts. The final `DictionaryEntries_endOfTable` pointer is the exclusive end
of the inclusive data range (`$0747C7-$0748D8 DATA`), which is file offset
`$0748D9`; the runtime reads a token until the next pointer, so this is the
end boundary rather than a pointer to the final byte. The raw source comment
at `$0748D8` is retained in the report.

```bash
uv run zelda-suite verify-text-dictionary-pointers \
  "base_game_roms/Legend of Zelda, The - A Link to the Past (U) [!].smc" \
  --output /tmp/text-dictionary-pointer-verification.json
```

Review `pointer_table.mismatch_count`, each entry's expected/actual bytes,
`target_offset_basis`, and `source_findings`. The `.You` extent discrepancy
(2-byte comment-derived source extent versus 6 declared payload bytes) remains
a separate warning. The terminal-pointer rule is based on the pinned source's
inclusive data-range comment and its next-code boundary; it does not resolve
the `.You` directive mismatch or prove this local image is canonical. Zero
pointer mismatches establish byte agreement only for this supplied image and
the candidate rules the tool applies. The verifier still does not read fragment
payload bytes, decode text, establish ROM provenance, or resolve the consumer's
`Text_DictionaryPointers` versus the visible `DictionaryPointers` declaration
name. Do not treat a matching result as clean-ROM certification.

## Encoded text-message byte comparison

Use the pinned disassembly blocks with an authorized local 1 MiB headerless
image:

```bash
uv run zelda-suite verify-text-message-bytes \
  "base_game_roms/Legend of Zelda, The - A Link to the Past (U) [!].smc" \
  --block reference/AsarUSALTTPDisassembly/Bank1C.asm Message_Data '$0E0000' '$0E7F29' \
  --block reference/AsarUSALTTPDisassembly/Bank0E.asm Message_DataExtra '$075F40' '$076E21' \
  --output /tmp/text-message-byte-verification.json
```

Review `summary.mismatch_byte_count`, the per-message `entries`, the
byte-level `mismatches`, and `source_findings`. The verifier accepts only
literal hexadecimal `db` bytes in the bounded source regions and does not
evaluate assembler expressions or decode message text. Its sequential offsets
are derived from source declarations; offset comments, block ranges, and ROM
provenance are not independently trusted. A result with zero byte mismatches
is evidence of agreement for that supplied image and the declared candidate
ranges only, not proof of a canonical ROM or verified message semantics.

## One-command read-only report bundle

After setting `ROM` in the current shell as shown in step 1, the bundled
runner can execute the supported read-only checks and preserve their output:

```bash
bash scripts/verify-rom-readonly.sh "$ROM"
```

It creates a fresh temporary report directory by default. To choose a report
directory, pass a second argument that does not already exist:

```bash
bash scripts/verify-rom-readonly.sh "$ROM" "/tmp/zelda-rom-checks-2026-10-29"
```

The script first writes `rom-inspection.json` and the two source-only hidden-item
reports. If the input is not exactly 1,048,576 bytes, it records why byte
comparisons were blocked and exits without running them. For a correctly sized
input it runs the self-diff, scalar-table verification in formats v1 and v2,
overworld hidden-item byte checks, dungeon-room pointer checks, text-dictionary
pointer checks, and encoded text-message byte checks. The `checks.tsv` file
records each command's exit status; all available findings are preserved even
when an individual check returns nonzero.

The runner never writes or normalizes the ROM. A zero exit status means only
that these commands returned success for this file and these source-derived
candidate offsets; it does not establish canonical ROM provenance, emulator
bootability, or correctness of untested semantics. Review each JSON report,
especially any source-commented offset mismatches, rather than shifting offsets
to force a pass.

## Diagnosing pointer mismatches from a report bundle

If either pointer verifier reports mismatches, print just the relevant fields
from its saved report before changing source annotations. Set `REPORT_DIR` to
the directory printed by `verify-rom-readonly.sh`:

```bash
REPORT_DIR="/tmp/zelda-rom-checks.41ihIf"
python - "$REPORT_DIR" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])

dungeon = json.loads(
    (root / "dungeon-room-pointer-verification.json").read_text(encoding="utf-8")
)
print("Dungeon pointer mismatches:", dungeon["pointer_table"]["mismatch_count"])
for item in dungeon["mismatches"]:
    print({
        key: item.get(key)
        for key in (
            "table_index", "pointer_entry_file_offset", "pointer_expression",
            "target_label", "target_source_file_offset", "expected_cpu_address",
            "expected_hex", "actual_hex", "reason",
        )
    })

dictionary = json.loads(
    (root / "text-dictionary-pointer-verification.json").read_text(encoding="utf-8")
)
print("Dictionary pointer mismatches:", dictionary["pointer_table"]["mismatch_count"])
for item in dictionary["mismatches"]:
    print({
        key: item.get(key)
        for key in (
            "table_index", "pointer_entry_file_offset", "pointer_expression",
            "target_fragment_label", "target_fragment_file_offset",
            "candidate_pointer_word", "expected_hex", "actual_hex", "reason",
        )
    })
print("Dictionary source findings:")
for item in dictionary["source_findings"]:
    print(item)
PY
```

These summaries expose the candidate address and actual bytes without printing
the ROM or creating a ROM slice. Keep the report's local SHA-256 alongside
any notes so results from different input files are not conflated. A mismatch
by itself does not tell you whether the source-commented offset is wrong or
whether the file is a different revision; verify the relationship from source
and trusted reference evidence before changing a candidate.

## What is and is not implemented

Currently available: ROM metadata inspection, file-backed byte-diffing,
source-only table/pointer/inventory export, export validation, read-only
verification of registered scalar-table literals, the overworld hidden-item
pointer/record region, the dungeon-room long-pointer table, text-dictionary
pointer words, and raw encoded text-message bytes, plus ROM-free project
initialization/storage tests. The text verifier commands report candidate
byte comparisons only; their source offsets and ROM provenance are not
independently verified, and the message command does not decode text.

Not yet implemented/verified: general semantic ROM extraction into editable
overworld/dungeon/item schemas; an edit-to-ROM build pipeline; ROM writer and
patch generation; emulator boot/smoke tests; trusted US-ROM hash validation;
local-ROM runs for the dictionary/message commands; and successful
YAZE/z3ed or z3cli operations against the local image.

Record the outputs from steps 1–7 and tool help from step 9 when reporting
results. Do not upload or commit the ROM, a ROM slice, or a raw binary dump.
