# ZeldaProject

A Claude-driven, RPG Maker-style authoring suite for *The Legend of Zelda: A Link to the Past*.

- **Agent instructions:** see [`CLAUDE.md`](./CLAUDE.md)
- **Plan:** see [`ROADMAP.md`](./ROADMAP.md)
- **Tool/project catalog:** see [`RESEARCH.md`](./RESEARCH.md)

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

See [`docs/doctor.md`](./docs/doctor.md) for diagnostics, [`docs/project-format.md`](./docs/project-format.md) for the SQLite/JSON project format, [`docs/disassembly-parser.md`](./docs/disassembly-parser.md) for source-level pointer-table inspection, and [`docs/asset-loader.md`](./docs/asset-loader.md) for validating source-export JSON.
