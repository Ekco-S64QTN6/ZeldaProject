# Project format and initialization

The canonical project file is SQLite, with a stable JSON export for review in
Git. This follows [ADR 0001](./decisions/0001-project-data-format.md). SQLite
is authoritative; JSON is generated from it and must not become a competing
source of truth.

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

## Schema version 1

The initial database contains two tables:

- `project`: singleton project metadata, JSON format version, creation time,
  expected base-ROM filename, and nullable verified ROM hash.
- `schema_version`: migration history, seeded with the current schema version.

The database and export contain metadata only at this stage. Overworld, dungeon,
items, text, sprites, audio, and extracted-data tables will be introduced with
Phase 1 schema/extraction work rather than guessed into the initial database.

## JSON export contract

`export_project(database_path)` reads the SQLite database and writes a JSON
snapshot beside it. It sorts object keys, uses UTF-8, prevents non-standard
JSON numeric values, ends with a single newline, and atomically replaces the
previous export. Re-exporting an unchanged database produces byte-identical
JSON. The top-level `format` and `format_version` identify the export contract;
`schema_version` identifies the SQLite schema/migration state.

Project databases (`.db`) stay ignored by Git. JSON exports under `project/`
are intentionally allowed by `.gitignore` so the canonical export can be
reviewed and committed when appropriate.
