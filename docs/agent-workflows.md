# Agent workflow and human-approval contract

**Status:** Host-neutral reference workflow for the current project-bound MCP
server. It documents the server's actual boundary and a recommended operating
procedure; it does not claim that a specific desktop/IDE host, live session,
model endpoint, or external tool integration has been tested.

## Session model

Run one `zelda-suite-mcp` process for one project database and one registered
asset manifest. Begin an authoring session with `project_get_context` to read
validation status, source metadata, semantic-model counts, and the exact project
revision without dumping full record arrays. Prefer absolute paths in the host launch configuration:

~~~bash
uv sync --extra agent
uv run zelda-suite-mcp \
  --database /absolute/path/to/project/my-hack.db \
  --registry /absolute/path/to/ZeldaProject/data/extracted/manifest.json
~~~

The server resolves and binds both paths during startup. Tool arguments cannot
switch projects, choose another registry, or supply arbitrary filesystem
paths. To work on another project, stop the process and start a new server
with that project's database. Do not multiplex projects through one process.

The server is request-oriented rather than a durable agent-session store:
handlers read the bound project when called, and the server does not persist
conversation history, a multi-step plan, user identity, or approval state.
SQLite is the canonical project state; successful applied operations refresh
the canonical JSON sidecar. A host should maintain the user conversation and
the current task plan, but it must re-read project state after every applied
mutation rather than trusting stale context.

Every mutation preview includes `project_revision`, a SHA-256 fingerprint of
the complete canonical project content. For an MCP apply, pass that exact value
as `expected_project_revision` with `apply=true`. The server recomputes the
fingerprint after acquiring SQLite's `BEGIN IMMEDIATE` write lock and rejects
the apply if any canonical project data changed since the preview. A stale
proposal must be previewed and approved again.

The fingerprint is an optimistic-concurrency guard, not an authentication
credential, a signed approval, or a user-identity token. The server does not
know who approved a proposal; the host must still obtain explicit approval for
the displayed change. The Python mutation APIs accept the expected revision
optionally, while the MCP surface requires it for every `apply=true` call.

Use one active writer per project during an edit workflow and verify after
applying. The revision check protects the SQLite mutation from stale project
state, but the server still does not implement multi-user locking or a durable
approval/session store.

## Tool permissions

The current MCP surface has three practical permission groups:

- **Read-only project inspection:** `project_get_context`, `project_validate`,
  `project_list_source_assets`, `project_get_source_asset`,
  `overworld_list_hidden_items`, `overworld_find_hidden_items`,
  `dungeon_list_chest_records`, `dungeon_find_chest_records`, and
  `dungeon_audit_chest_room_references`. These may be called to inspect the
  bound project.
- **Preview-first project mutation:** `overworld_update_hidden_item_record`,
  `dungeon_update_chest_record`, `overworld_create_custom_hidden_item`,
  `overworld_update_custom_hidden_item`, and
  `overworld_delete_custom_hidden_item`. Call first without `apply` or with
  `apply=false`; show the preview and obtain approval for the exact change
  before applying.
- **Not exposed:** ROM reads/writes, patching, building, source-asset imports,
  arbitrary file access, and registry/database selection. Do not infer these
  capabilities or emulate them through unrelated tools.

The server's Pydantic schemas enforce field types and bounds. Mutating calls
default to a read-only preview. Setting `apply=true` persists project-local
SQLite/JSON data only; it does not update a ROM. The server does not implement
user authentication, a permission database, or an approval service. Those are
host responsibilities, not server guarantees.

## Human-approval gate

For every mutation, the host should follow this sequence:

1. **Establish context.** Confirm which project is bound, call
   `project_get_context`, and check `valid`, source/model provenance, counts,
   and the returned `project_revision`. Use `project_validate` for a focused
   validation re-check and inspect individual records only when needed. For
   source-backed data, retain the source label/index and provenance fields.
2. **Preview.** Call the mutation tool without `apply=true`. Require a
   successful response with `dry_run=true`; inspect its `before`, `proposed`,
   `changed_fields`, source baselines, and evidence flags.
3. **Explain the exact change.** Show the record identity and the `proposed` raw
   field values with their `source_references`. Imported overworld rows cite
   the source file/hash, label/line/expression, file-offset annotation, and
   linked area pointer metadata. Chest records cite the table declaration,
   source line/expression, and candidate entry-offset annotation. For
   project-authored hidden items, show the
   `area_source_references` (or before/proposed lists) with area target labels
   and pointer annotations, explicitly saying these are not ROM-verified
   offsets. Across all three mutation domains, distinguish source annotations
   from verified ROM offsets; every citation reports `rom_offsets_verified=false`
   and `rom_bytes_read=false`. Explain unresolved semantics: chest item bytes
   are not canonical
   item IDs; chest room values are not confirmed playable-room IDs; hidden-item
   value bytes are source-consumer masks/selectors, not item names.
4. **Obtain explicit approval.** Ask the user to approve this exact preview.
   Approval to explore or to find a candidate is not approval to persist it.
   Do not infer approval from silence or from a broad project goal.
5. **Apply the same operation.** Call the same tool with the same
   target/field arguments, the exact `project_revision` returned by the
   approved preview as `expected_project_revision`, and `apply=true`. The
   server checks the fingerprint under its SQLite write lock. If it rejects a
   stale revision, obtain a new preview and new approval; do not retry the old
   token or silently apply the changed proposal.
6. **Verify.** Re-read the changed record, validate the project, and run the
   relevant read-only audit. Report the project-local mutation accurately and
   state that the ROM was not changed.

A failed preview, missing source model, invalid reference, unexpected `before`
value, or changed proposal is a stop condition. Do not attempt a compensating
write automatically. Explain the failure and ask for a new decision.

## Reference workflows

The following are tool-call sequences a host can implement. The values are
illustrative raw fields, not a claim about canonical game-item identities.
These examples document the intended operating procedure; no external natural
language host session has been completed or counted as an end-to-end
integration test. CI now also starts the server as a subprocess and exercises
initialization, tool discovery, revision-bound mutation, and validation with
the MCP SDK `ClientSession`; that checks the stdio protocol but is not a test
of a particular end-user host.

In the examples below, tool_name{...} means an MCP tool call with the
shown JSON arguments; an empty argument object is written as tool_name{}.

### 1. Inspect and edit one dungeon chest

1. Call `project_validate{}`.
2. Read a candidate with `dungeon_list_chest_records{"table_index":5}`.
3. Preview one raw field change, for example
   `dungeon_update_chest_record{"table_index":5,"item_value":36}`.
4. Present the source index, source literal/baselines, and `proposed` item byte.
   State that byte 36 is raw and has no resolved item name.
5. After approval, call the same mutation with
   `expected_project_revision` set to the exact `project_revision` returned
   by the preview and `apply=true`.
6. Re-read index 5, call `project_validate{}`, and run
   `dungeon_audit_chest_room_references{}` when room references are relevant.

### 2. Find and update an imported overworld hidden-item row

1. Call `overworld_find_hidden_items{"area_index":12}` to inspect rows linked
   to that area. Narrow by `record_index`, `coordinate_word`, or `value_byte` when
   the user identifies a specific target.
2. Preview the requested bounded coordinate/value edit with
   `overworld_update_hidden_item_record`; do not include `apply=true`.
3. Show the `before`/`proposed` values, source label/index, area aliases, and
   consumer classification. Do not rename the raw byte as an item.
4. After explicit approval, apply the same arguments with the preview's exact
   `project_revision` as `expected_project_revision` and `apply=true`.
5. Re-read the row with `overworld_find_hidden_items`, inspect the affected
   area with `overworld_list_hidden_items`, and call `project_validate{}`.

### 3. Add a project-authored hidden-item record

1. Check the relevant areas with `overworld_list_hidden_items`.
2. Preview `overworld_create_custom_hidden_item` with the complete non-empty
   area list, coordinate word, and raw value byte. For example:
   `{"area_indices":[12,13],"coordinate_word":4660,"value_byte":5}`.
3. Explain that the `proposed` record is project-authored, has no source record
   index or canonical item ID, and adds links to both selected areas.
4. After approval, call the same operation with the preview's exact
   `project_revision` as `expected_project_revision` and `apply=true`.
5. Verify the returned custom ID with
   `overworld_find_hidden_items{"custom_record_id":1}` (use the ID returned by
   the apply response), inspect both area views, and call `project_validate{}`.

## Remaining integration gates

- Select and test a concrete MCP host and its configuration; the server has
  only been exercised by its repository contract tests.
- Demonstrate at least three natural-language workflows in a real host
  session. The sequences above are documented examples, not completed demos.
- Add durable approval/session identity and multi-user coordination if the
  project later supports shared-host or multi-user editing; revision fingerprints
  guard stale state but are not signed approvals or authorization.
- Keep deterministic ROM diffs, a verified writer, and emulator checks outside
  the MCP contract until their roadmap gates are met.

See the MCP server contract (mcp-server.md) for transport, tool schemas, and
dependency compatibility details.
