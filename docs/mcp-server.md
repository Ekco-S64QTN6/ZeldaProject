# Optional project-bound MCP server

The `zelda-suite-mcp` entry point exposes a deliberately small subset of the
project API to an MCP-compatible agent. It is an optional transport, not a
requirement for the Python package, CLI, project store, or tests outside the
development extra.

## Install and start

Install the optional agent dependency:

```bash
uv sync --extra agent
```

The server requires an existing project database and never guesses which
project to open:

```bash
uv run zelda-suite-mcp \
  --database project/my-hack.db \
  --registry data/extracted/manifest.json
```

The asset registry can be selected at startup through `--registry` or
`ZELDA_SUITE_ASSET_REGISTRY`. Use an absolute manifest path in an MCP host
whose working directory is not the repository root. Both paths are fixed when
the server starts; no tool accepts a database or registry path.

The same database can be selected through `ZELDA_SUITE_PROJECT_DB`:

```bash
ZELDA_SUITE_PROJECT_DB=project/my-hack.db \
ZELDA_SUITE_ASSET_REGISTRY=data/extracted/manifest.json \
  uv run zelda-suite-mcp
```

The process uses stdio transport. Configure the MCP host to launch this
executable as a local stdio server and keep its stdin/stdout reserved for MCP
traffic. Use an absolute database path in the host configuration if its working
directory is not the repository root. The server does not download, locate, or
open a ROM. The module can also be launched directly for development and
protocol testing:

```bash
python -m zelda_suite.mcp.server --database PATH --registry PATH
```

## Tool contract

| Tool | Behavior |
| --- | --- |
| `project_get_context` | Return validation, the canonical project revision, source-asset metadata, and compact overworld/dungeon model provenance and counts from one read-only snapshot; omit record arrays and asset payloads. |
| `project_validate` | Validate SQLite and its canonical JSON sidecar; no writes. |
| `project_list_source_assets` | List imported source-asset metadata. |
| `project_get_source_asset` | Read one project source-asset snapshot by key. |
| `overworld_list_hidden_items` | Read the model, optionally filtered to one area index. |
| `overworld_find_hidden_items` | Read-only AND-filtered search across imported and project-authored records by area, record ID, coordinate word, and/or value byte. |
| `overworld_update_hidden_item_record` | Preview coordinate/value edits to one imported source record; persist only with `apply=true` and the preview's `expected_project_revision`. |
| `dungeon_list_chest_records` | Read all 168 chest records or select one record by bounded table index 0–167. |
| `dungeon_find_chest_records` | Find records by one or more raw item-byte (0–255), room-value (0–32767), and big-chest-flag filters; read-only and source-order preserving. |
| `dungeon_audit_chest_room_references` | Read-only join of current chest room values to the registered object/door pointer tables, retaining source baselines and findings. |
| `dungeon_update_chest_record` | Preview a bounded item-byte, room-value, and/or big-chest-flag edit; persist only with `apply=true` and the preview's `expected_project_revision`. |
| `overworld_create_custom_hidden_item` | Preview a project-authored record and one-or-more area links; persist only with `apply=true` and the preview's `expected_project_revision`. |
| `overworld_update_custom_hidden_item` | Preview coordinate/value edits and/or replacement of the complete area-link set; persist only with `apply=true` and the preview's `expected_project_revision`. |
| `overworld_delete_custom_hidden_item` | Preview deletion by custom-record ID; persist only with `apply=true` and the preview's `expected_project_revision`. |

The `project_get_context` tool is the recommended first read for an agent
session. It validates the SQLite project and canonical JSON sidecar, then
returns project identity, the exact canonical `project_revision` used by
revision-bound mutation previews, source-asset metadata, and summary-only
semantic-model provenance/counts. The values are derived from one read-only
SQLite transaction. Asset payloads and individual records are omitted; the
source file names shown are registered source metadata, not local file paths.
A semantic model that has not been imported is returned as `null`. No ROM
bytes are read.

The server is bound to one resolved database path and one resolved asset
registry path at startup. No tool accepts a database path, registry path, or
arbitrary filesystem path, and tool inputs are validated with strict Pydantic
fields. The custom hidden-item tools retain the underlying API's bounds: area indexes 0–127, coordinate words 0–65534 (with `$FFFF` reserved as
the list sentinel), and value bytes 0–255. A custom record remains separate from
the 351 imported source records and can link to several area slots.

The `overworld_find_hidden_items` tool requires at least one filter. It can
search source rows by `record_index` (0–350), custom rows by
`custom_record_id` (positive integer), and either kind by `area_index`
(0–127), `coordinate_word` (0–65534), or `value_byte` (0–255). Source and
custom IDs cannot be supplied together; all other supplied fields combine with
AND semantics. Results keep imported rows in record-index order and custom
rows in custom-record-ID order, with source provenance and evidence flags.
These are raw fields and consumer annotations, not canonical item identities.
The operation is read-only and does not open a ROM.

## Write and approval boundary

All mutation calls default to a read-only preview (`apply=false`). Each preview
returns `project_revision`, a lowercase SHA-256 fingerprint over the complete
canonical project payload. Every MCP apply must supply that exact preview value
as `expected_project_revision` alongside `apply=true`. The server recalculates
the fingerprint inside the `BEGIN IMMEDIATE` SQLite write transaction before
any mutation. If a different writer or operation has changed any canonical
project data, the server rejects the stale apply without changing SQLite or
JSON; the caller must preview again and obtain approval for the new proposal.
A fingerprint is a concurrency guard, not proof of user approval or an
authentication token. The server still relies on the host to obtain explicit
user approval and does not implement user identity or authorization.

A successful `apply=true` commits a project-local SQLite change and refreshes canonical JSON.
Custom hidden-item updates retain omitted fields; supplying `area_indices`
replaces the complete non-empty area-link set. Custom update/delete accept only
a custom-record ID; neither can edit nor delete an imported source record.

Custom hidden-item create/update/delete previews include `area_source_references`
for the linked overworld areas. Create and delete responses return that list;
update previews return `before_area_source_references` and
`proposed_area_source_references`, while applied updates return the before and
current lists. Each reference carries the area index, the pinned source file,
revision and hash, its target label, and source-annotated pointer-entry,
target, and sentinel file offsets. These citations identify the source area
table context for a project-authored record; they are not a source offset for
the custom record itself. Each entry explicitly sets `rom_offsets_verified`
and `rom_bytes_read` to false. Treat these as source annotations, not verified
ROM locations.

`overworld_update_hidden_item_record` accepts a source record index from 0–350
and at least one of `coordinate_word` (0–65534) or `value_byte` (0–255).
`$FFFF` remains reserved as a list sentinel. Applied edits preserve the
original source coordinate/value fields and all existing area aliases while
recalculating consumer classification from the changed raw byte. The preview
and applied response include `source_references`: the imported source row's
file/revision/hash, source label/line/expression, source-offset annotation, and
each linked area's target label plus pointer/target/sentinel annotations.
Every cited offset is explicitly unverified against ROM bytes. A value byte is
not a canonical item ID. The change updates SQLite/JSON only.

`dungeon_audit_chest_room_references` reports every chest against both
registered 320-entry pointer tables, grouping repeated room values and surfacing
out-of-range values or object/door target-label mismatches. It includes the
current edited room value and the immutable source room baseline. The report is
source-metadata arithmetic only: candidate offsets, room payload bytes, item
names, and the playable-room set remain unverified; it never reads or writes a
ROM. The tool needs the asset registry fixed at server startup.

`dungeon_list_chest_records` returns the full model when `table_index` is
omitted. Supplying an index from 0–167 returns only that entry, with its source
revision, source hash, and evidence flags.

`dungeon_update_chest_record` accepts a table index from 0–167 and at least
one of `item_value` (0–255), `room_value` (0–32767), or `is_big_chest` (boolean).
It recomposes the packed 24-bit value while preserving the original source
literal and source field baselines. The preview and applied response include
`source_references` for the source table declaration/range and selected row:
source file/revision/hash, table label, raw range annotation, source line and
expression, and the candidate entry-offset annotation. These are source
annotations, not ROM-verified locations. The room value remains a raw
pointer-table index candidate, not a confirmed playable-room identifier, and
the item byte is not a canonical item-name mapping. The update changes
SQLite/JSON only.

The preview responses for all five mutation tools include `project_revision`.
The `expected_project_revision` input is available only with `apply=true` and
is required for MCP persistence. Its schema accepts exactly 64 lowercase hex
characters. The tool schema also describes `apply` as requiring explicit user
approval and `expected_project_revision` as the exact preview fingerprint to
return on apply. These descriptions are sent to MCP clients, so agents see the
required call sequence in tool metadata rather than relying only on external
documentation. The underlying Python APIs accept the expected revision
optionally for callers that need the same optimistic-concurrency check outside
MCP.

The `dungeon_find_chest_records` tool requires at least one filter and applies
all supplied filters as an AND query to the current project model. It returns
matching records in their original table-index order with source provenance,
immutable baselines, and ROM evidence flags. It never edits the project or
resolves item bytes to canonical item names or room values to playable rooms.

The host/agent workflow must obtain human approval before sending `apply=true`.
The server's instructions describe this expectation, but the server does not
implement a separate user-authentication, authorization, or approval service.
The recommended one-project-per-process session model, permission groups,
preview/approval/apply sequence, and reference workflows are documented in
[agent-workflows.md](./agent-workflows.md).
Source-asset imports, arbitrary file access, ROM reads, ROM writes, patching,
saving, and rebuilding remain outside the tool surface. Continue using the
Python API/CLI for supported operations that are not yet mapped to MCP. Do not
infer broader capabilities from the presence of the server.

## SDK compatibility

This implementation imports `mcp.server.fastmcp.FastMCP` from the MCP Python
SDK v1 line and declares the optional dependency as `mcp>=1.28.1,<2`. The
upper bound is intentional: SDK v2 is now the current stable line and renamed
the server API to `MCPServer`; the current code has not been migrated to that
API. Keep the upper bound until a tested v2 migration is made. The v1 line is
maintained separately for critical fixes and security patches. See the
[official v1 documentation](https://py.sdk.modelcontextprotocol.io/v1/),
[official v2 migration guide](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/migration.md),
and [v2 changes](https://py.sdk.modelcontextprotocol.io/whats-new/).

## Tests and limitations

`tests/test_mcp_server.py` checks the tool schema, database and registry binding,
read-only project inspection, full and single-entry chest reads, chest/room
audit, default preview behavior, revision fingerprints on every mutation
preview, missing/stale revision rejection, explicit imported-row, custom-record,
and chest edit commits, structured source citations on every mutation class,
area alias visibility/replacement, immutable source baselines, source-row count
preservation, and absence of ROM/import tools.

`tests/test_mcp_stdio.py` also checks `project_get_context` over stdio and
asserts that its project revision matches the immediately following mutation
preview. `tests/test_mcp_stdio.py` launches the module as a subprocess and
connects with the MCP Python SDK `ClientSession` over the real stdio transport.
It imports
both semantic models into a temporary project, then runs revision-bound chest
editing, imported overworld editing, and project-authored hidden-item
create/update/delete in one session. It verifies the source citation envelopes,
area-link readback, removal of deleted custom records, and final project
validation. This is an SDK-level process smoke test; it does not establish
compatibility with a particular desktop/IDE host, model endpoint, or `z3cli`.
Those remain separate roadmap gates.
