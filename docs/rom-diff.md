# Deterministic byte-diff contract

The `zelda_suite.diff` package provides a pure byte-buffer comparison for the
Phase 1 ROM diff harness. It does **not** read files, write ROMs, generate IPS
patches, or bypass the extraction/writing layers.

## Use

```python
from zelda_suite.diff import compare_bytes

# Buffers are supplied by the approved extraction/write layer.
diff = compare_bytes(original_bytes, modified_bytes)
print(diff.to_json())
```

To compare a slice of a larger file while keeping offsets relative to that
file, provide `base_offset`:

```python
diff = compare_bytes(original_slice, modified_slice, base_offset=0x8000)
```

`base_offset` is the absolute offset of byte zero of the supplied buffers.
All reported region offsets are absolute and use half-open intervals:
`[start_offset, end_offset_exclusive)`.

## Region grouping

The algorithm compares bytes at the same offsets. It collects adjacent changed
positions into one region; an unchanged byte splits regions. For example, if
only offsets 3, 4, and 9 change, the result contains a two-byte region and a
separate one-byte region.

For same-size buffers this matches a conventional byte-level patch review. If
one buffer is longer, appended bytes become a region at the old end. If one is
shorter, removed bytes are recorded as a region whose modified payload is
empty. The implementation is not a sequence-alignment algorithm; an insertion
in the middle will appear as a run of changed offsets after the insertion.

Each region stores:

- Absolute start offset and exclusive end offset.
- Original and modified bytes as uppercase hexadecimal without separators.
- Original and modified payload lengths.
- Number of differing positions in that contiguous region.

The top-level `zelda-suite-byte-diff` JSON format version 1 includes original
size, modified size, net size delta, total changed-byte count, region count, and
the ordered region list. JSON uses sorted keys, fixed indentation, and a final
newline to keep output deterministic for Git review.

## Safety boundary

This module accepts immutable `bytes` and the bytes-like `bytearray` and
`memoryview` inputs; it does not mutate them. It only compares buffers already
provided by a caller. Per the repository's source-of-truth rules, loading ROM
bytes belongs in the extraction layer and writing belongs in the writing
layer. A byte diff is an audit artifact, not authorization to write the ROM.

The helper does not decide whether a changed byte is semantically valid. Before
any write is connected to it, the writer must cite the project data row and
pinned disassembly location, support dry-run, and pass the project's planned
emulator smoke test.

## Tests

Synthetic tests cover unchanged buffers, separated/adjacent changes, appends,
truncations, absolute offset reporting, stable JSON, and invalid inputs. They
require no ROM or ROM-derived fixture.


## File-backed CLI

The read-only CLI compares a canonical-size base ROM with a locally built
candidate image and wraps the byte diff with input metadata:

```bash
uv run zelda-suite diff-rom \
  "base_game_roms/Legend of Zelda, The - A Link to the Past (U) [!].smc" \
  project/build/candidate.smc \
  --output /tmp/candidate-diff.json
```

The command reads both files only through `zelda_suite.extract.read_rom_bytes`,
requires the base image to be exactly 1 MiB, and records each input filename,
size, and SHA-256 beside the deterministic diff. A candidate whose size suggests
a 512-byte copier header is rejected rather than silently shifted. The output
uses the `zelda-suite-rom-file-diff` version-1 format described by
[the export schema](./schemas/rom-file-diff-export.schema.json).

This command compares two ROM images; it does not apply project edits, write
ROMs, generate IPS patches, or prove that a candidate boots. Mapping semantic
project changes to ROM bytes and an emulator verification loop remain separate
roadmap work.
