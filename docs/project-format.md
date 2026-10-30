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

## Schema version 4

A current project has ten tables:

- `project`: singleton project metadata, JSON format version, creation time,
  expected base-ROM filename, and nullable base-ROM SHA-256.
- `schema_version`: migration history. Fresh projects record v1, v2, and v3.
- `source_asset`: named source-export snapshots with format/version,
  source filename(s)/revision, import timestamp, canonical JSON, and SHA-256.
- `overworld_hidden_item_model`: source file/revision/hash and the pinned
  consumer/table labels for the imported semantic domain.
- `overworld_hidden_item_area`: all 128 pointer-table slots and their source
  target and sentinel metadata. Separate slots remain separate even when they
  alias the same data list.
- `overworld_hidden_item_record`: 351 three-byte source records. Immutable
  source coordinate/value fields are preserved beside editable coordinate and
  value fields. Consumer-class fields are recomputed when a value byte changes.
- `overworld_hidden_item_area_record`: ordered many-to-many relationships
  between areas and records, preserving shared-pointer aliases.
- `overworld_hidden_item_replacement_word`: the four raw words from
  `Overworld_SecretTileType` that extended selectors can refer to.
- `dungeon_chest_model`: source revision/hash, original range annotation, and
  packed-table dimensions for the registered `Dungeon_ChestData` inventory.
- `dungeon_chest_record`: all 168 packed 24-bit records with immutable source
  expression, literal, item byte, room value, and big-chest flag preserved beside
  editable fields. Database checks require both source and edited fields to
  recompose to their corresponding packed 24-bit values.

The first semantic model deliberately does not name canonical item IDs: the
third byte is classified from the pinned `Overworld_RevealSecret` consumer
as a zero value, ordinary secret-state mask, or extended selector. Coordinates
and bytes can be edited in the project; ROM bytes cannot be written. Project
JSON format v4 adds `overworld_hidden_items` and `dungeon_chests` members (null
until imported, otherwise structured snapshots of the semantic model and source
baselines). Dungeon chest edits recompose the three-byte literal from the top-byte
item value, low-15-bit room value, and bit-15 big-chest flag. Values remain raw:
item names are not resolved, room/pointer relationships remain source metadata,
and candidate source offsets are not asserted as verified ROM offsets. Both
semantic models modify SQLite plus the JSON sidecar only; no ROM-writing path is
implemented. The existing `source_assets` metadata API remains available.

## Migrate older projects

Schema-v1, schema-v2, and schema-v3 projects must be upgraded explicitly:

```bash
uv run zelda-suite migrate-project project/my-hack.db
```

A v1 project migrates sequentially through schema v2 (adds `source_asset`),
schema v3 (adds overworld hidden-item tables), and schema v4 (adds dungeon
chest tables). A v2 project migrates through v3 and v4; a v3 project gets v4
directly. The migrations preserve project metadata, record every schema version,
and rewrite the JSON sidecar as format v4. Each individual schema-version
transition starts an explicit SQLite
`BEGIN IMMEDIATE` transaction before its DDL, then commits the new tables and
matching `project.format_version` and `schema_version` metadata together. If
any statement in a transition fails, SQLite rolls back that transition,
including tables created earlier in the same step. A multi-step v1-to-v4
migration commits each version separately; if a later step fails, the database
remains at the last successfully committed schema version and the migration
can be retried from there. The JSON sidecar is refreshed only after all
database transitions commit. A sidecar-write failure does not undo the database
migration; rerun `migrate-project` to regenerate the export. Migration is not
automatic
during validation or asset import. Use `--json PATH` to write the export to
a non-default location. Running the command on a current project does not
change the database; it refreshes the JSON sidecar from SQLite.

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

## Editable overworld hidden-item records

Import the pinned source-derived area/record model into an initialized project:

```bash
uv run zelda-suite import-overworld-hidden-items \
  project/my-hack.db reference/AsarUSALTTPDisassembly/Bank1B.asm
uv run zelda-suite list-overworld-hidden-items project/my-hack.db --area-index 0
uv run zelda-suite update-overworld-hidden-item project/my-hack.db 0 \
  --coordinate-word '$1234' --value-byte '$84'
uv run zelda-suite validate project/my-hack.db
```

Record indexes refer to the stable source record order, not to canonical item
IDs. The CLI validates coordinate words (`$FFFF` is reserved as the area's list
terminator), validates bytes, and reclassifies an edited byte using the pinned
source consumer. Source values/coordinates remain alongside edits so the JSON
export shows exactly which records differ from their baseline. Aliased areas
can reference the same record through the relationship table. Re-importing
an existing model is refused unless `--replace` is supplied; replacement resets
project-local edits to the imported source. This model is an authoring-data
foundation only: it does not calculate ROM write locations, modify the ROM,
or resolve canonical item IDs.
## Editable dungeon chest records

Import the registered source inventory, inspect records, and edit the raw packed fields:

```bash
uv run zelda-suite import-dungeon-chest-data project/my-hack.db
uv run zelda-suite list-dungeon-chest-records project/my-hack.db --table-index 5
uv run zelda-suite list-dungeon-chest-records project/my-hack.db --room-value '$32'
uv run zelda-suite update-dungeon-chest-record project/my-hack.db 0 \
  --item-value '$AA' --room-value '$1234' --big-chest
uv run zelda-suite validate project/my-hack.db
```

Table indexes are the source-order indexes from the 168-entry inventory; they
are not stable semantic chest IDs. The top byte remains a raw item value because
canonical item names have not been resolved. The low 15 bits remain a raw room
value; the project also reports the consumer-derived `room_pointer_index` and
three-byte table displacement, without asserting candidate ROM offsets as
verified. The original packed literal, expression, and unpacked fields are never
overwritten by edits. Re-import refuses to clobber edits unless `--replace` is
supplied explicitly. This model is for project authoring only and never writes
or patches ROM bytes.
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
format and digest, semantic hidden-item relationships and consumer classifications,
and exact agreement with the JSON export. It returns a nonzero exit code and a
`[FAIL]` line for problems; a consistent project prints `[OK]`. To check an
export stored elsewhere, pass `--json PATH`.

Validation never repairs or rewrites either artifact. To intentionally refresh
a stale JSON sidecar without changing data, run `zelda-suite migrate-project`
on the current database or call `export_project(database_path)` from Python.

 
## Audit project-local chest room references

After importing `Dungeon_ChestData`, run the project-aware audit:

```bash
uv run zelda-suite audit-project-dungeon-chest-room-references project/my-hack.db
uv run zelda-suite audit-project-dungeon-chest-room-references project/my-hack.db \
  --fail-on-findings
uv run zelda-suite audit-project-dungeon-chest-room-references project/my-hack.db \
  --output /tmp/chest-room-reference-audit.json
```

Unlike `audit-dungeon-chest-room-references`, which audits the immutable source
inventory, this command reads the current editable values from the project's
SQLite chest model and joins each current room value to the registered
`RoomData_ObjectDataPointers` and `RoomData_DoorDataPointers` source exports.
Each row includes the original source room value, current room value, edit
status, table indexes, source labels, and source-annotated pointer offsets. An
edited value that no longer selects a slot in both 320-entry pointer tables is
reported as an error; `--fail-on-findings` returns exit status 1 when findings
exist. Output files are created exclusively and are never overwritten.

The report is pinned to disassembly revision
`347c23f9fc019c72d32da537c9cb235f468d021d`. It reads the project database and
validated source metadata only. Candidate chest/pointer offsets and room
payload bytes are not thereby verified, room values are not converted into
canonical room names, the 296-versus-320 playable-room issue remains open, and
the command never reads or writes ROM bytes. Its separate contract is
[`project-dungeon-chest-room-reference-audit.schema.json`](./schemas/project-dungeon-chest-room-reference-audit.schema.json).
