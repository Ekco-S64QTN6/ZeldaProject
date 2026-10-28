# ZeldaProject

A Claude-driven, RPG Maker-style authoring suite for *The Legend of Zelda: A Link to the Past*.

- **Agent instructions:** see [`CLAUDE.md`](./CLAUDE.md)
- **Plan:** see [`ROADMAP.md`](./ROADMAP.md)
- **Tool/project catalog:** see [`RESEARCH.md`](./RESEARCH.md)
- **Contributing:** see [`CONTRIBUTING.md`](./CONTRIBUTING.md)
- **Changes and versioning:** see [`CHANGELOG.md`](./CHANGELOG.md) and [`docs/versioning.md`](./docs/versioning.md)

**Project status (2026-10-28):** Early-stage foundation and source-metadata tooling. The repository has a SQLite project store with explicit schema migration and validated source-export persistence, source-only extractors, a validated named-asset registry, read-only ROM inspection, and file-based byte-diff utilities. The source inventory now includes the 320-entry dungeon room pointer table and all 266 source-labelled room payload declarations across Bank03, Bank0A, and Bank1F. Semantic game editing and ROM writing/rebuilding are **not implemented yet**. Source inventories preserve unknowns and mismatched source annotations rather than guessing at binary meanings. See the [current roadmap](./ROADMAP.md) and [extracted-data catalog](./docs/extracted-data.md). To import a committed asset by its validated registry name, run `uv run zelda-suite import-extracted-asset project/my-hack.db falling-prize-item-values`. The overworld High/Low source inventories can be checked with `uv run zelda-suite validate-overworld-payload-pairs data/extracted/overworld-payloads-bank0b.json data/extracted/overworld-payloads-bank0c.json`.

## Quickstart

Prepare dependencies and initialize a project without a game ROM:

```bash
bash scripts/setup.sh --name my-hack
# Windows PowerShell: .\scripts\setup.ps1 -Name my-hack
```

The setup script prefers `uv` and falls back to a Python 3.12+ virtual
environment when needed. It refuses to overwrite an existing project, then
validates the created SQLite database and JSON sidecar. It does not download,
copy, open, or modify a ROM.

For local ROM/tool diagnostics later, place an authorized clean US dump at
`base_game_roms/Legend of Zelda, The - A Link to the Past (U) [!].smc` and run
`just doctor`. That command fails when the ROM is missing or incorrectly sized;
its size check is not proof of ROM provenance or correctness, and tool checks
only confirm executables are on `PATH`. Run `zelda-suite inspect-rom PATH`
for read-only size, SHA-256, header assessment, and LoROM mapping diagnostics.
These checks have not been established by repository CI; see the open Phase 0
gates in [`ROADMAP.md`](./ROADMAP.md). Setup and CI remain ROM-independent.
For a staged, read-only local-ROM smoke test and selected table-byte checks,
follow [`docs/real-rom-verification.md`](./docs/real-rom-verification.md).

For setup and diagnostics, see [`docs/install.md`](./docs/install.md) and [`docs/doctor.md`](./docs/doctor.md). For read-only local-ROM checks, including `zelda-suite verify-rom-tables` and `zelda-suite verify-overworld-hidden-items`, see [`docs/real-rom-verification.md`](./docs/real-rom-verification.md). Also see [`docs/project-format.md`](./docs/project-format.md) for the SQLite/JSON project format, [`docs/disassembly-parser.md`](./docs/disassembly-parser.md) for pointer-table inspection, [`docs/data-table-parser.md`](./docs/data-table-parser.md) for raw `db`/`dw`/`dl` tables, [`docs/asset-loader.md`](./docs/asset-loader.md) for validating source-export JSON, [`docs/project-assets.md`](./docs/project-assets.md) for importing validated source exports into a project, [`docs/rom-image-inspection.md`](./docs/rom-image-inspection.md) for local ROM metadata and LoROM offset mapping, [`docs/rom-diff.md`](./docs/rom-diff.md) for file-backed ROM diff usage, and [`docs/extracted-data.md`](./docs/extracted-data.md) for committed source-derived table exports.
