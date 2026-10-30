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
uv run zelda-suite-mcp --database project/my-hack.db
```

The same database can be selected through `ZELDA_SUITE_PROJECT_DB`:

```bash
ZELDA_SUITE_PROJECT_DB=project/my-hack.db uv run zelda-suite-mcp
```

The process uses stdio transport. Configure the MCP host to launch this
executable as a local stdio server and keep its stdin/stdout reserved for MCP
traffic. Use an absolute database path in the host configuration if its working
directory is not the repository root. The server does not download, locate, or
open a ROM.

## Tool contract

| Tool | Behavior |
| --- | --- |
| `project_validate` | Validate SQLite and its canonical JSON sidecar; no writes. |
| `project_list_source_assets` | List imported source-asset metadata. |
| `project_get_source_asset` | Read one project source-asset snapshot by key. |
| `overworld_list_hidden_items` | Read the model, optionally filtered to one area index. |
| `dungeon_list_chest_records` | Read the imported packed dungeon-chest model. |
| `overworld_create_custom_hidden_item` | Preview a project-authored record and one-or-more area links; persist only with `apply=true`. |
| `overworld_update_custom_hidden_item` | Preview coordinate/value edits and/or replacement of the complete area-link set; persist only with `apply=true`. |
| `overworld_delete_custom_hidden_item` | Preview deletion by custom-record ID; persist only with `apply=true`. |

The server is bound to one resolved database path at startup. No tool accepts a
database path or arbitrary filesystem path, and tool inputs are validated with
strict Pydantic fields. The custom hidden-item tools retain the underlying API's
bounds: area indexes 0–127, coordinate words 0–65534 (with `$FFFF` reserved as
the list sentinel), and value bytes 0–255. A custom record remains separate from
the 351 imported source records and can link to several area slots.

## Write and approval boundary

All custom create/update/delete calls default to a read-only preview
(`apply=false`). Setting `apply=true` commits a project-local SQLite change and
refreshes canonical JSON. Updates retain omitted fields; supplying
`area_indices` replaces the complete non-empty area-link set. Update and
delete accept only a custom-record ID; neither can edit or delete an imported
source record. The host/agent workflow must obtain human
approval before sending `apply=true`. The server's instructions describe this
expectation, but the server does not implement a separate user-authentication,
authorization, or approval service.

The tool surface does not expose imported source-row updates, dungeon chest
edits, source-asset imports, arbitrary file access, ROM reads, ROM writes,
patching, saving, or rebuilding. Continue using the Python API/CLI for supported
operations that are not yet mapped to MCP. Do not infer broader capabilities
from the presence of the server.

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

`tests/test_mcp_server.py` checks the tool schema, database binding, read-only
project inspection, default preview behavior, explicit create/update/delete
commits, area alias visibility/replacement, source-row count preservation, and
absence of ROM/import tools. CI runs these contract tests with the other Python checks.

This does not establish compatibility with a specific model host, a live
session, a particular model endpoint, or `z3cli`. Those integrations remain
separate roadmap gates.
