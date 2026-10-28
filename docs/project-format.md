# Project format and initialization

The canonical project is SQLite, with a stable JSON export for review in Git.
This follows [ADR 0001](./decisions/0001-project-data-format.md). SQLite is
authoritative; JSON is generated from it and must not become a competing source
of truth.

Project JSON format and SQLite schema versions are separate contracts; see the [versioning policy](./versioning.md).

## Create a project

From the repository root, run:

```bash
uv run zelda-suite init my-hack
```

This creates:

- `project/my-hack.db` — SQLite database.
- `project/my-hack.json` — UTF-8, two-space-indented JSON export with sorted keys
  and a trailing newline.

Use `--workspace PATH` to place these beneath another workspace root. Project
names must be 1–64 characters, start with an ASCII letter or digit, and contain
only letters, digits, hyphens, or underscores. Initialization refuses to
overwrite either existing artifact.

Initializing a project does not require or open a ROM. It records the expected
canonical US ROM filename, but leaves its SHA-256 unset until a later extraction
workflow explicitly verifies the base ROM. ROM files are never copied into a
project or added to Git.

## Schema version 2

A current project has three tables:

- `project`: singleton project metadata, JSON format version, creation time,
  expected base-ROM filename, and nullable verified ROM hash.
- `schema_version`: schema version history. A fresh v2 project records the
  baseline v1 and current v2 versions.
- `source_asset`: named source-export snapshots with format/version,
  source filename(s)/revision, import timestamp, canonical JSON, and SHA-256.
  Multi-source exports use a sorted, semicolon-delimited source-file value.

The `source_asset` table stores only validated source-derived JSON metadata
exports, such as pointer or scalar-data table descriptions. It does not store
ROM images, binary payload slices, or semantically edited game-system records.
The project remains a scaffold for authoring work; semantic overworld/dungeon
editing and a ROM writer are not implemented.

## Migrate a schema-v1 project

Projects created before schema v2 must be migrated explicitly:

```bash
uv run zelda-suite migrate-project project/my-hack.db
```

The migration adds `source_asset`, upgrades the project JSON format version to
2, preserves the project metadata and v1 migration record, and writes the v2
JSON sidecar. Migration is not automatic during validation or asset import.
Use `--json PATH` to write the export to a non-default location. Running the
command on an already-current project does not change the database; it refreshes
the JSON sidecar from SQLite.

## Import and query source assets

```bash
uv run zelda-suite import-extracted-asset \
  project/my-hack.db falling-prize-item-values

# Explicit-path import remains available for temporary validated exports:
uv run zelda-suite import-source-asset \
  project/my-hack.db receive-item-values \
  data/extracted/item-receipt-values.json

uv run zelda-suite list-source-assets project/my-hack.db
uv run zelda-suite get-source-asset project/my-hack.db receive-item-values
uv run zelda-suite validate project/my-hack.db
```

Asset keys must be 1–96 characters, begin with an ASCII letter or digit, and
contain only letters, digits, dots, hyphens, or underscores. Each import passes
through the same versioned source-export validator used by the extractor tools.
For committed assets, `import-extracted-asset` additionally resolves the asset
through the manifest and checks the registered format, revision, and record
count before storing it.
The normalized payload is stored with its SHA-256 digest and source provenance;
the JSON sidecar is refreshed after the database write. Duplicate keys are
refused unless `--replace` is supplied deliberately. Replacing a key updates
that asset snapshot rather than preserving multiple versions under one key.

The Python functions `import_source_asset()`, `list_source_assets()`, and
`get_source_asset()` provide the same operations. Read operations validate
the stored export format, canonical JSON representation, denormalized source
metadata, and SHA-256 digest before returning data. See
[Project source assets](./project-assets.md) for the full contract.

## JSON export contract

`export_project(database_path)` reads SQLite and writes a canonical JSON
snapshot beside it. It sorts object keys, uses UTF-8, rejects non-standard JSON
numeric values, ends with a single newline, and atomically replaces the
previous export. Re-exporting an unchanged database produces byte-identical
JSON. The top-level `format` / `format_version` identify the project JSON
contract, while `schema_version` identifies the database schema. Version 2
adds a `source_assets` array ordered by asset key; each record includes asset
metadata, digest, import timestamp, and validated source payload.

Project databases (`.db`) stay ignored by Git. JSON exports under `project/`
are intentionally allowed by `.gitignore` so the canonical export can be
reviewed and committed when appropriate.

## Validate a project

Run:

```bash
uv run zelda-suite validate project/my-hack.db
```

The validator opens SQLite in read-only mode and checks SQLite integrity,
required schema tables, foreign-key consistency, supported format/schema
versions, canonical project-name/ROM metadata, every stored source asset's
format and digest, and exact agreement with the JSON export. It returns a
nonzero exit code and a `[FAIL]` line for problems; a consistent project prints
`[OK]`. To check an export stored elsewhere, pass `--json PATH`.

Validation never repairs or rewrites either artifact. To intentionally refresh
a stale JSON sidecar without changing data, run `zelda-suite migrate-project`
on the current database or call `export_project(database_path)` from Python.
