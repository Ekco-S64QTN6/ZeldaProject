# Agent workflow and human-approval contract

**Status:** Host-neutral reference workflow for the current project-bound MCP
server. It documents the server's actual boundary and a recommended operating
procedure; it does not claim that a specific desktop/IDE host, live session,
model endpoint, or external tool integration has been tested.

## Session model

Run one `zelda-suite-mcp` process for one project database and one registered
asset manifest. Prefer absolute paths in the host launch configuration:

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

Use one active writer per project during an edit workflow. Preview calls are
read-only and do not reserve the project for a later apply. There is no preview
token or revision precondition that binds an `apply=true` call to a previous
preview. Re-preview immediately before applying, avoid concurrent edits from
another session, and verify the result afterward. The underlying applied
project edits use SQLite write transactions, but that does not make an old
preview safe to apply after another writer has changed the project.

## Tool permissions

The current MCP surface has three practical permission groups:

- **Read-only project inspection:** `project_validate`,
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
   `project_validate`, and inspect the relevant record/model. For source-backed
   data, retain the source label/index and provenance fields.
2. **Preview.** Call the mutation tool without `apply=true`. Require a
   successful response with `dry_run=true`; inspect its `before`, `proposed`,
   `changed_fields`, source baselines, and evidence flags.
3. **Explain the exact change.** Show the record identity and the `proposed` raw
   field values. Explain unresolved semantics: chest item bytes are not
   canonical item IDs; chest room values are not confirmed playable-room IDs;
   hidden-item value bytes are source-consumer masks/selectors, not item names.
4. **Obtain explicit approval.** Ask the user to approve this exact preview.
   Approval to explore or to find a candidate is not approval to persist it.
   Do not infer approval from silence or from a broad project goal.
5. **Apply the same operation.** Re-check the current record/model, repeat the
   preview if anything has changed, then call the same tool with the same
   target/field arguments and `apply=true`. If the current preview differs
   from the approved proposal, stop and request approval for the new proposal.
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
integration test.

In the examples below, tool_name{...} means an MCP tool call with the
shown JSON arguments; an empty argument object is written as tool_name{}.

### 1. Inspect and edit one dungeon chest

1. Call `project_validate{}`.
2. Read a candidate with `dungeon_list_chest_records{"table_index":5}`.
3. Preview one raw field change, for example
   `dungeon_update_chest_record{"table_index":5,"item_value":36}`.
4. Present the source index, source literal/baselines, and `proposed` item byte.
   State that byte 36 is raw and has no resolved item name.
5. After approval of that exact preview, re-read/preview and call the same
   mutation with `apply=true`.
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
4. After explicit approval, repeat the preview against current state and apply
   the same arguments with `apply=true`.
5. Re-read the row with `overworld_find_hidden_items`, inspect the affected
   area with `overworld_list_hidden_items`, and call `project_validate{}`.

### 3. Add a project-authored hidden-item record

1. Check the relevant areas with `overworld_list_hidden_items`.
2. Preview `overworld_create_custom_hidden_item` with the complete non-empty
   area list, coordinate word, and raw value byte. For example:
   `{"area_indices":[12,13],"coordinate_word":4660,"value_byte":5}`.
3. Explain that the `proposed` record is project-authored, has no source record
   index or canonical item ID, and adds links to both selected areas.
4. After approval, repeat the preview and call the same operation with
   `apply=true`.
5. Verify the returned custom ID with
   `overworld_find_hidden_items{"custom_record_id":1}` (use the ID returned by
   the apply response), inspect both area views, and call `project_validate{}`.

## Remaining integration gates

- Select and test a concrete MCP host and its configuration; the server has
  only been exercised by its repository contract tests.
- Demonstrate at least three natural-language workflows in a real host
  session. The sequences above are documented examples, not completed demos.
- Add stronger revision-bound preview/apply semantics before supporting
  concurrent writers or treating previews as durable approval artifacts.
- Keep deterministic ROM diffs, a verified writer, and emulator checks outside
  the MCP contract until their roadmap gates are met.

See the MCP server contract (mcp-server.md) for transport, tool schemas, and
dependency compatibility details.
