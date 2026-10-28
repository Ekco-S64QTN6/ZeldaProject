# Project source assets

Schema-v2 project databases can preserve validated source-export JSON snapshots
inside SQLite. This provides a stable, queryable boundary between source
inspection and later semantic game-data modeling.

A stored source asset consists of a caller-supplied safe key, the export format
and version, source filename and revision, import timestamp, canonical JSON
payload, and SHA-256 of that canonical UTF-8 payload. The loader validates the
source-export schema before the database is changed. On read, the asset store
revalidates the payload and verifies that the digest and stored provenance
metadata agree.

This feature stores source-derived JSON metadata only. It does not ingest ROM
images or `incbin` binary payloads, infer semantic item IDs, or enable edits to
game-system records.

## Commands

Create a new project:

```bash
uv run zelda-suite init my-hack
```

Import one supported source export under a stable project-local key:

```bash
uv run zelda-suite import-source-asset \
  project/my-hack.db item-values data/extracted/item-receipt-values.json
```

List asset metadata without printing all stored payloads:

```bash
uv run zelda-suite list-source-assets project/my-hack.db
```

Fetch a stored asset and its provenance:

```bash
uv run zelda-suite get-source-asset project/my-hack.db item-values
```

Duplicate keys are rejected by default. Replacing an existing snapshot requires
the explicit `--replace` flag. Each successful import refreshes the project JSON
sidecar so the exported snapshot remains reviewable in Git.

## Import a registered asset by name

For assets already listed in `data/extracted/manifest.json`, prefer the
manifest-backed command. It validates the registered name, selected filename,
format, pinned source revision, and record count before persistence:

```bash
uv run zelda-suite import-extracted-asset \
  project/my-hack.db falling-prize-item-values
```

The project key defaults to the registry asset name. Use `--asset-key KEY` to
choose a different project-local key, `--registry PATH` for a different
validated registry, and `--replace` only when deliberately refreshing an
existing key. This is safer than copying a JSON path manually because the
registry's metadata is checked before the payload is stored.

## Python API

```python
from zelda_suite.project import (
    get_source_asset,
    import_source_asset,
    list_source_assets,
)

import_source_asset(
    "project/my-hack.db",
    "item-values",
    "data/extracted/item-receipt-values.json",
)
assets = list_source_assets("project/my-hack.db")
values = get_source_asset("project/my-hack.db", "item-values")
print(assets[0]["sha256"], values["payload"]["entry_count"])
```

The list operation returns metadata only; the get operation also returns the
validated source payload. Keys are 1–96 ASCII characters, start with a letter
or digit, and contain only letters, digits, dots, hyphens, and underscores.

## Migration and integrity

Projects using schema v1 must be upgraded explicitly before importing assets:

```bash
uv run zelda-suite migrate-project project/my-hack.db
```

Migration updates the database schema and project JSON format to version 2
without discarding project metadata. Validation does not auto-migrate. Running
the migration command against a current project refreshes its JSON sidecar
without changing the database schema.

`zelda-suite validate` checks SQLite integrity, the required schema, project
metadata, every persisted source asset's validated export format, canonical
JSON representation and SHA-256, and exact consistency with the sidecar JSON.
No asset import or query reads ROM bytes.
