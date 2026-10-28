# ZeldaProject

A Claude-driven, RPG Maker-style authoring suite for *The Legend of Zelda: A Link to the Past*.

- **Agent instructions:** see [`CLAUDE.md`](./CLAUDE.md)
- **Plan:** see [`ROADMAP.md`](./ROADMAP.md)
- **Tool/project catalog:** see [`RESEARCH.md`](./RESEARCH.md)

**Project status:** Early-stage foundation and source-metadata tooling. The repository has a SQLite project store with explicit schema migration and validated source-export persistence, source-only extractors, a validated named-asset registry, read-only ROM inspection, and file-based byte-diff utilities. The source inventory now includes the 320-entry dungeon room pointer table and 75 Bank0A room payload declarations. Semantic game editing and ROM writing/rebuilding are **not implemented yet**. Source inventories preserve unknowns and mismatched source annotations rather than guessing at binary meanings. See the [current roadmap](./ROADMAP.md) and [extracted-data catalog](./docs/extracted-data.md). To import a committed asset by its validated registry name, run `uv run zelda-suite import-extracted-asset project/my-hack.db falling-prize-item-values`. The overworld High/Low source inventories can be checked with `uv run zelda-suite validate-overworld-payload-pairs data/extracted/overworld-payloads-bank0b.json data/extracted/overworld-payloads-bank0c.json`.

## Quickstart

```bash
# 1. Drop a clean US ROM here:
#    base_game_roms/Legend of Zelda, The - A Link to the Past (U) [!].smc

# 2. Set up the Python environment
uv sync            # or: python -m venv .venv && .venv/bin/pip install -e ".[dev]"

# 3. Initialize an editable project (no ROM read/write occurs)
uv run zelda-suite init my-hack

# 4. Verify the generated project files
uv run zelda-suite validate project/my-hack.db

# 5. Verify tooling and ROM presence
just doctor        # or: .venv/bin/zelda-suite doctor
```

See [`docs/doctor.md`](./docs/doctor.md) for diagnostics, [`docs/project-format.md`](./docs/project-format.md) for the SQLite/JSON project format, [`docs/disassembly-parser.md`](./docs/disassembly-parser.md) for pointer-table inspection, [`docs/data-table-parser.md`](./docs/data-table-parser.md) for raw `db`/`dw`/`dl` tables, [`docs/asset-loader.md`](./docs/asset-loader.md) for validating source-export JSON, [`docs/project-assets.md`](./docs/project-assets.md) for importing validated source exports into a project, [`docs/rom-image-inspection.md`](./docs/rom-image-inspection.md) for local ROM metadata and LoROM offset mapping, [`docs/rom-diff.md`](./docs/rom-diff.md) for file-backed ROM diff usage, and [`docs/extracted-data.md`](./docs/extracted-data.md) for committed source-derived table exports.
