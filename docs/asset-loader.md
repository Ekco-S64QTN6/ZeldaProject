# Source-export asset loader

The asset loader gives downstream tools one entry point for the versioned source
exports produced by the Phase 1 inspection commands. It validates each payload
before returning it to a caller.

## Python API

```python
from zelda_suite.extract import load_source_export

export = load_source_export("/tmp/room-object-pointers.json")
print(export["format"], export["format_version"])
```

Supported version-1 formats are pointer-table exports from
`zelda-suite inspect-pointer-table`, `incbin` inventories from
`zelda-suite inspect-incbin`, scalar data-table exports from
`zelda-suite inspect-data-table`, and text dictionary fragment inventories
from `zelda-suite inspect-text-dictionary`. The loader checks required fields,
rejects unknown keys and unsupported versions, confirms record counts, and
validates cross-field invariants including index/offset sequences, directive
widths, source revisions, source extents, and bounded table relationships.

Dictionary fragment inventories preserve source annotation mismatches rather
than rejecting them as inherently invalid. The loader checks that each recorded
match flag accurately reflects the recorded source extent and directive size;
a `false` flag is valid provenance for an unresolved source-layout discrepancy.

## CLI

The same checks are available through:

```bash
uv run zelda-suite validate-source-export /tmp/room-object-pointers.json
uv run zelda-suite validate-source-export /tmp/text-dictionary-fragments.json
```

The command prints `[OK]` for a supported consistent export and returns a
nonzero exit code with a diagnostic for invalid data.

## Scope

This is the roadmap's source-export validation foundation, not yet a loader for
editable game data. It accepts metadata about source declarations and does not
open ROMs, resolve symbol targets from ROM memory, open `incbin` payload
paths, decode dictionary/message streams, perform extraction, or permit edits.
Future schema versions and game-data formats should be added through explicit
validators and fixture-backed tests rather than weakening current checks.
