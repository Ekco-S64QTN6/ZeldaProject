# Source-export asset loader

The initial asset loader gives downstream tools one entry point for the source
exports produced by the Phase 1 inspection commands. It validates the payload
before returning it to a caller.

## Python API

```python
from zelda_suite.extract.asset_loader import load_source_export

export = load_source_export("/tmp/room-object-pointers.json")
print(export["format"], export["format_version"])
```

Supported formats are version 1 pointer-table exports from
`zelda-suite inspect-pointer-table` and `incbin` inventories from
`zelda-suite inspect-incbin`. The loader checks required fields, rejects
unknown keys and unsupported versions, confirms record counts, and validates
cross-field invariants such as pointer-table index/offset sequences and the
relationship between incbin source ranges and annotated sizes.

The CLI provides the same checks:

```bash
uv run zelda-suite validate-source-export /tmp/room-object-pointers.json
```

It prints `[OK]` for a supported consistent export and returns a nonzero exit
code with a diagnostic for invalid data.

## Scope

This is a first step toward the roadmap's named asset loader, not yet a loader
for editable game data. It accepts only the two source-inspection export
formats available today. It does not open ROMs, resolve pointer targets, open
`incbin` payload paths, perform extraction, or permit edits. Future schema
versions and game-data formats should be added through explicit validators and
fixture-backed tests rather than weakening current checks.
