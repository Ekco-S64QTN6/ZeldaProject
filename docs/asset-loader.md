# Named source-export asset loader

The asset loader gives downstream tools one entry point for versioned source
exports, and a registry so callers can load committed data by stable name.

## List and load by name

From the repository root:

```python
from zelda_suite.extract import list_extracted_assets, load_extracted_asset

for asset in list_extracted_assets():
    print(asset["name"], asset["subsystem"], asset["record_count"])

items = load_extracted_asset("falling-prize-item-values")
messages = load_extracted_asset("text-message-index")
print(items["entries"][0]["expression"])
print(messages["message_count"])
```

The default registry is `data/extracted/manifest.json`. Tools using another
workspace can pass an explicit registry path to either function:

```python
table = load_extracted_asset(
    "text-dictionary-fragments",
    registry_path="/workspace/project/data/extracted/manifest.json",
)
```

`list_extracted_assets()` validates and returns registry metadata without
opening each asset file. `load_extracted_asset(name)` resolves only a registered
kebab-case name, loads the associated JSON, applies its format-specific source
export validator, and checks that the export's format, source revision, and
record count match the registry. Filenames must be simple JSON basenames that
stay directly inside the registry directory; names or registry entries cannot
request arbitrary filesystem paths.

## Registry contract

The registry file uses format `zelda-suite-asset-registry`, version 1. Each
entry provides a stable name, relative JSON filename, supported export format,
pinned source revision, record count, subsystem, and short description. The
JSON shape is defined in
[asset-registry.schema.json](./schemas/asset-registry.schema.json). The initial
registry covers the five falling-prize lookup arrays, the 98-entry text
dictionary pointer/fragment metadata, the 397-entry source text message index, and the 68-entry SpriteActive3 dispatch table.

Add an asset by committing its validated export, adding exactly one registry
entry, adding test coverage for its provenance/count, and documenting any
known discrepancy. Do not register ROMs, ROM-derived byte slices, or decoded
message payloads as source-only exports.

## Explicit-path API

The lower-level `load_source_export(path)` remains available when a tool is
working with a temporary export that is not registered. It validates pointer
tables, incbin inventories, scalar data tables, dictionary fragment inventories,
text message indexes, and sprite dispatch tables before returning the parsed payload.

```python
from zelda_suite.extract import load_source_export

export = load_source_export("/tmp/text-message-index.json")
print(export["format"], export["format_version"])
```

## Validation and scope

The CLI provides the same format checks:

```bash
uv run zelda-suite validate-source-export /tmp/text-message-index.json
```

This loader manages source-derived metadata, not editable game data. It does
not read ROM bytes, resolve symbols from ROM memory, open incbin payload paths,
decode dictionary/message streams, perform extraction, or permit edits. Future
schemas should be added with explicit validators and fixture-backed tests
rather than weakening current checks.
