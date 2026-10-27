# Source-export asset loader

The asset loader gives downstream tools one entry point for the versioned source
exports produced by the Phase 1 inspection commands. It validates each payload
before returning it to a caller.

## Python API

```python
from zelda_suite.extract import load_source_export

export = load_source_export("/tmp/text-message-index.json")
print(export["format"], export["format_version"])
```

Supported version-1 formats are pointer-table exports from
`zelda-suite inspect-pointer-table`, `incbin` inventories from
`zelda-suite inspect-incbin`, scalar data-table exports from
`zelda-suite inspect-data-table`, text dictionary fragment inventories from
`zelda-suite inspect-text-dictionary`, and source text message indexes from
`zelda-suite inspect-text-messages`.

The loader rejects unknown keys and unsupported versions, verifies record
counts and source revisions, and checks cross-field invariants including entry
index/offset sequences, directive widths, directive-vs-annotated source
extents, and message starts computed from preceding directive byte counts.
Offset annotations that disagree with source-derived sequential offsets are
preserved as diagnostics; a `false` comparison flag is valid provenance for an
unresolved source comment. Similarly, a message block whose declared byte
total differs from its annotated range is recorded as a mismatch rather than
rewritten.

## CLI

The same checks are available through:

```bash
uv run zelda-suite validate-source-export /tmp/room-object-pointers.json
uv run zelda-suite validate-source-export /tmp/text-dictionary-fragments.json
uv run zelda-suite validate-source-export /tmp/text-message-index.json
```

The command prints `[OK]` for a supported internally consistent export and
returns a nonzero exit code with a diagnostic for invalid data. It does not
claim that source address comments have been verified against a local ROM.

## Scope

This is the source-export validation foundation, not yet a loader for editable
game data. It accepts metadata about source declarations and does not read ROM
bytes, resolve symbols from ROM memory, open `incbin` payload paths, decode
dictionary/message streams, perform extraction, or permit edits. Future schema
versions and game-data formats should be added through explicit validators and
fixture-backed tests rather than weakening current checks.
