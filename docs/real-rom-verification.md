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
file fingerprint, not proof of provenance.

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

## 6. Run the ROM-independent regression suite

```bash
uv run pytest -q
uv run ruff check src tests
uv run mypy src
```

These cover existing parsers, source exports, project store/migration,
inspection, diff, and CLI behavior. They are not substitutes for testing
YAZE/z3ed on your ROM.

## 7. Install and inspect external-tool capabilities

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

## What is and is not implemented

Currently available: ROM metadata inspection, file-backed byte-diffing,
source-only table/pointer/inventory export, export validation, read-only
verification of registered numeric scalar-table literals, and ROM-free
project initialization/storage tests.

Not yet implemented/verified: general semantic ROM extraction into editable
overworld/dungeon/item schemas; an edit-to-ROM build pipeline; ROM writer and
patch generation; emulator boot/smoke tests; trusted US-ROM hash validation;
and successful YAZE/z3ed or z3cli operations against the local image.

Record the outputs from steps 1–5 and tool help from step 7 when reporting
results. Do not upload or commit the ROM, a ROM slice, or a raw binary dump.
