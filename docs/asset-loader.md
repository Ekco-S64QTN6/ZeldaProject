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
receipt_layout = load_extracted_asset("item-receipt-layout")
print(receipt_layout["entries"][0]["target_address"]["expression"])
print(receipt_layout["dungeon_mask_count"])
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
[asset-registry.schema.json](./schemas/asset-registry.schema.json). The current
registry has 26 named exports across item lookup/receive tables, text, sprite
dispatch, music, overworld, and dungeon source inventories. The
`item-receipt-layout` asset is a validated positional join of six raw
receive-item arrays plus a separate 14-word mask table; it does not resolve
canonical item IDs.

Add an asset by committing its validated export, adding exactly one registry
entry, adding test coverage for its provenance/count, and documenting any
known discrepancy. Do not register ROMs, ROM-derived byte slices, or decoded
message payloads as source-only exports.

## Explicit-path API

The lower-level `load_source_export(path)` remains available when a tool is
working with a temporary export that is not registered. It validates pointer
tables, incbin inventories, scalar data tables, joined receive-item layouts,
dictionary fragment inventories, text message indexes, sprite dispatch tables,
and music-track indexes before returning the parsed payload.

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

The source-export loader is also the validation boundary used by
[project source-asset persistence](./project-assets.md). The project store can
snapshot a validated export into SQLite with provenance and a content digest.
For committed assets, `import-extracted-asset` accepts the registered manifest
name and retains the registry's format/revision/count checks before persisting.
This does not turn source metadata into editable game-system records.

The loader and project asset store do not read ROM bytes, resolve symbols from
ROM memory, open incbin payload paths, decode dictionary/message streams, or
perform binary extraction. Future schemas should be added with explicit
validators and fixture-backed tests rather than weakening current checks.
