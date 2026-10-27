# ZeldaProject

A Claude‑driven, RPG Maker‑style authoring suite for *The Legend of Zelda: A Link to the Past*.

- **Agent instructions:** see [`CLAUDE.md`](./CLAUDE.md)
- **Plan:** see [`ROADMAP.md`](./ROADMAP.md)
- **Tool/project catalog:** see [`RESEARCH.md`](./RESEARCH.md)

## Quickstart

```bash
# 1. Drop a clean US ROM here:
#    base_game_roms/Legend of Zelda, The - A Link to the Past (U) [!].smc

# 2. Set up the Python environment
uv sync            # or: python -m venv .venv && .venv/bin/pip install -e ".[dev]"

# 3. Verify tooling
just doctor        # or: .venv/bin/zelda-suite doctor
