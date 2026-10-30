# Authoring API

Status: **partially implemented**. The current public Python surface supports
bounded source-preserving edits for overworld hidden-item records and packed
dungeon chest fields, plus dry-run-first create/update/delete for project-authored
overworld hidden-item additions. The optional, project-bound stdio MCP server
also exposes custom hidden-item create/update/delete with previews by default;
broader editing, ROM writes, and external model-host workflows remain future
work.

## Current project functions

- `initialize_project()`, `migrate_project()`, `validate_project()`, and
  `export_project()` manage the SQLite-canonical project and JSON sidecar.
- `import_overworld_hidden_item_model()`,
  `get_overworld_hidden_item_model()`, and
  `update_overworld_hidden_item()` operate on the 351 source-preserving rows.
- `create_custom_overworld_hidden_item()`,
  `update_custom_overworld_hidden_item()`, and
  `delete_custom_overworld_hidden_item()` manage project-authored additions.
  They default to `dry_run=True`. Updates can replace the complete set of
  area links or retain it when omitted, and can independently edit the raw
  coordinate word/value byte. Custom records remain separate from source row
  indexes, baselines, and source alias rows.
- `import_dungeon_chest_data()`, `get_dungeon_chest_model()`, and
  `update_dungeon_chest_record()` operate on the 168 source-indexed packed
  chest entries. Editable fields are raw item byte, low-15-bit room value, and
  big-chest flag; the packed 24-bit literal is recomposed with storage checks.
- `audit_project_dungeon_chest_room_references()` joins the current project
  room values to the validated source object/door-pointer exports. It preserves
  each original source room value and edit status and reports out-of-range room
  references and pointer target-label mismatches.

## Command-line entry points

Use the CLI wrapper to produce the same versioned project-reference report:

```bash
uv run zelda-suite audit-project-dungeon-chest-room-references project/my-hack.db
uv run zelda-suite audit-project-dungeon-chest-room-references project/my-hack.db \
  --fail-on-findings
```

The CLI commands `create-custom-overworld-hidden-item`,
`update-custom-overworld-hidden-item`, and
`delete-custom-overworld-hidden-item` preview by default and require `--apply`
to persist. An update omits any field it should retain; repeating
`--area-index` replaces the complete many-to-many area-link set. The area-specific list command returns both imported source records
and separately identified custom records. All semantic edit operations update
SQLite and its JSON sidecar only;
they do not write ROM bytes. The project-aware audit reads SQLite and registered
source metadata but does not access the ROM. Source-commented pointer offsets
are not verified binary locations, item names remain unresolved, and the
playable-room count discrepancy remains open. The report schema is documented
in `docs/schemas/project-dungeon-chest-room-reference-audit.schema.json`.

## Design constraints for future operations

1. Every mutating call must support `dry_run=True` before it can write external
   artifacts; ROM writes remain prohibited until the explicit safeguards in
   `CLAUDE.md` are met.
2. Every response must cite the project record and supporting disassembly
   label/offset range while distinguishing source annotations from verified
   offsets.
3. Referential integrity must be enforced at the API and storage layers, not
   deferred to binary serialization.
4. New fields and operations require bounded validation, deterministic
   serialization, source baselines, regression tests, and explicit migration
   policy where the persisted format changes.


## Optional MCP transport

Install the `agent` extra and run `zelda-suite-mcp --database PATH` to
serve one existing project database over stdio. The process binds its database
path once at startup; no tool accepts a database or arbitrary filesystem path.
The initial tool set is:

- `project_validate`, `project_list_source_assets`, and
  `project_get_source_asset` for project validation and source metadata.
- `overworld_list_hidden_items` and `dungeon_list_chest_records` for
  bounded model reads.
- `overworld_create_custom_hidden_item`,
  `overworld_update_custom_hidden_item`, and
  `overworld_delete_custom_hidden_item` for project-authored hidden-item
  records. All default to `apply=false`; an explicit `apply=true` commits
  to SQLite and refreshes canonical JSON. Updates omit fields to retain their
  values, and an explicit `area_indices` list replaces all area links.

The MCP surface deliberately does not expose source-row updates, dungeon chest
edits, source-asset imports, arbitrary file access, ROM reads, or ROM writes.
The Python API and CLI remain available independently of the optional MCP
dependency. See [`mcp-server.md`](./mcp-server.md) for installation, startup,
host setup, and the complete security/verification boundary.
