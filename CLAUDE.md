# CLAUDE.md

Project context and operating instructions for Claude working in this repository.

---

## 1. What This Project Is

A **Claude‑driven, RPG Maker‑style authoring suite for The Legend of Zelda: A Link to the Past (SNES)**.

The end goal is a scriptable pipeline where Claude (or any agent) can:
- Read a clean ALttP ROM into a structured, human‑readable project data model.
- Make semantic edits (rooms, chests, overworld tiles, text, sprites, entrances) via a stable API.
- Rebuild and diff against the base ROM so every change is auditable.
- Eventually support "maker"‑style workflows (templates, bulk operations, patch export) beyond single edits.

This is **not** a wrapper around Hyrule Magic and **not** a ROM patcher. It is a data‑model‑first, agent‑native editor.

---

## 2. Canonical Assets

**Base ROM (US, the only one the build reads):**

```
base_game_roms/Legend of Zelda, The - A Link to the Past (U) [!].smc
```

- USA release, verified good dump, headerless.
- This is the single source of truth for the build. Do not substitute another ROM.

**Optional JP reference (not read by the build):**

```
base_game_roms/Zelda no Densetsu - Kamigami no Triforce (J) (V1.0).smc
```

- Present for diffing JP vs. US data later. Never read by the pipeline.

**Design lineage reference (read‑only, not read by the build):**

```
reference/parallel_worlds/         ← Parallel Worlds v1.23 artifacts (IPS, readme, credits)
reference/AsarUSALTTPDisassembly/  ← git submodule; ground truth for ROM semantics
```

Rules:

- **Do not commit ROMs** (`*.smc`, `*.sfc`) — they are in `.gitignore`.
- **Do not add** translations, bad dumps, hacks, or regional variants of the *base* game to `base_game_roms/`.
- The JP ROM is an explicit, allowed exception. Do not add others.
- Reference hacks go in `reference/`, never in `base_game_roms/`.

**Ground truth for ROM semantics:**
- `AsarUSALTTPDisassembly` (JaredBrian) — full US disassembly. Every byte‑level write must be validated against a label or table definition here.

---

## 3. Primary Tooling

| Tool | Role | Notes |
|---|---|---|
| **YAZE / `z3ed`** | Low‑level ROM interface (CLI + GUI) | Reference implementation for overworld/dungeon/graphics/palette/message access. Wrap behind an adapter; do not couple our code to its internals. |
| **`z3cli`** | Agent harness (MCP, session management, model routing) | Use as the backend for Phase 3 agent workflows. Verify Anthropic endpoint compatibility before relying on it. |
| **Asar** | 65816 assembler | For any ASM patches we insert. |
| **zcompress** | Graphics decompression/recompression | Reference for graphics round‑tripping. |
| **SpriteSomething** | Sprite import/export (ZSPR, PNG) | Wrap its CLI for the sprite authoring API. |

**Not dependencies:**
- Hyrule Magic, ZScream, Super Zelda Editor, Black Magic — domain references only. Do not build on them. (See §9 for why.)
- Lunar IPS — fine for Phase 4 release tooling; not part of the editing pipeline.
- HxD, Windhex — ad‑hoc debugging only.

---

## 4. Reference Projects (Read, Don't Depend On)

- **Z3R (`xander-haj/Z3R`)** — Extract‑to‑YAML → edit → rebuild‑assets pipeline. Closest existing data‑model architecture to what we want. Study `restool.py` and the YAML schema.
- **Super Zelda Editor (DMCP2143)** — 2 MB ROM support, multi‑layer room visualization, prefab rooms. Good source of editor‑core ideas.
- **Zelda Reloaded Maker** — Project‑file paradigm for Zelda 1; conceptual model for Phase 4 "maker" mode.
- **Solarus Engine** — Possible non‑SNES export target if the project outgrows SNES constraints.
- **`alttpr` randomizer ecosystem**, **Mudora**, **Archipelago ALttP integration** — Working examples of programmatic ROM read/write at scale. Useful for the verification harness.

---

## 5. Design Lineage

The aesthetic and technical direction is **the *Parallel Worlds* lineage**.

**Key collaborators and their post‑PW work to study:**

- **Euclid** — *Zelda3 Parallel Remodel*, *Tower of the Triforce*, BS Zelda restorations, AST dungeon editor.
- **SePH** — *Goddess of Wisdom*, *A Link to the Islands*, *A Link to the Proto*, lead hacker on **Conker's High Rule Tail**.
- **Con / Conn** — *Zelda3 IQ Test*, *Conker's High Rule Tail* ASM, *Conn's Ultimate ASM Pack*.
- **qwertymodo** — *A Link to the Past DX*, MSU‑1 ASM support, *Parallel Worlds* 10‑year anniversary update.
- **PuzzleDude** — *Parallel Remodel* supervisor, *IQ Test* series, *Conker's High Rule Tail* core team.

**Most important single reference:** ***Conker's High Rule Tail*** — the direct spiritual successor to *Parallel Worlds*, reuniting SePH, PuzzleDude, Euclid, and Conn. It pushed the SNES with new ASM for menus, HDMA, and MSU‑1. If a design decision is unclear, ask: *"What would CHRT do?"*

---

## 6. Repository Layout (Current)

```
/
├── CLAUDE.md
├── ROADMAP.md
├── RESEARCH.md
├── README.md
├── pyproject.toml
├── justfile
├── .gitignore
├── .gitmodules
├── base_game_roms/               ← locally supplied ROMs; ignored by Git
├── data/extracted/                ← committed source-derived metadata JSON + manifest
├── reference/
│   ├── README.md
│   ├── AsarUSALTTPDisassembly/   ← pinned git submodule; semantic source reference
│   └── parallel_worlds/           ← read-only reference documents and patch
├── project/                       ← local working projects; generated files ignored
├── src/zelda_suite/
│   ├── cli/main.py
│   ├── extract/                    ← read-only source/ROM inspection and export validation
│   ├── project/store.py            ← SQLite project metadata + JSON export
│   └── diff/rom_diff.py            ← file-backed ROM byte diff
├── tests/                          ← parser, export, CLI, project, and diff regression tests
└── docs/
    ├── api.md
    ├── project-format.md
    ├── extracted-data.md
    ├── asset-loader.md
    ├── incbin-inventory.md
    ├── rom-image-inspection.md
    ├── rom-diff.md
    ├── schemas/                    ← export contracts and discovery notes
    └── decisions/                  ← architecture decision records
```


**Project data format:** SQLite as canonical (`project/<name>.db`) with a JSON export on save for git diffing. See `docs/decisions/0001-project-data-format.md`. Do not change this without a new ADR.

---

## 7. Non‑Negotiable Rules

1. **Never write to the ROM without a validated diff.** Every write goes through `src/zelda_suite/write/`, which must produce a deterministic byte diff and pass an emulator smoke test (YAZE headless or equivalent).
2. **Cite your source.** Any proposed change must reference (a) the project data file/row and (b) the disassembly label / byte range in `AsarUSALTTPDisassembly`.
3. **Dry‑run first.** The authoring API must support a `dry_run=True` mode that reports intended changes without applying them. Default to dry‑run.
4. **Referential integrity.** A chest cannot point to a nonexistent item. An entrance cannot point to a nonexistent room. Enforce at the SQLite schema and the API layer, not the byte layer.
5. **Adapters, not dependencies.** YAZE, SpriteSomething, zcompress are wrapped behind `src/zelda_suite/adapters/`. If their APIs change, only the adapter changes.
6. **The data model is the source of truth.** The ROM is a build artifact. Never read raw ROM bytes outside `src/zelda_suite/extract/` and `src/zelda_suite/write/`.
7. **No legacy GUI tool assumptions.** Do not assume Hyrule Magic quirks are correct behavior. Trust the disassembly.

---

## 8. Workflow Conventions

- **One change = one commit.** The ROM diff goes in the commit body when the change affects ROM bytes.
- **Tests first for extraction logic.** Add a fixture before writing a parser.
- **Phase discipline.** Use `ROADMAP.md` as the current status ledger. Do not claim a phase exit criterion is met until implementation and evidence exist; label local-ROM or external-tool checks unverified when they have not been run.
- **Ask before adding dependencies.** Prefer stdlib and one well‑known library over a framework.
- **Log everything in `docs/`.** New schemas, new API functions, new ROM caveats.
- **Task runner:** `justfile` at repo root. Run `just` to list commands. `just doctor` is the canary; keep it green.

---

## 9. What NOT To Do

- ❌ **Do not add ROMs to `base_game_roms/` beyond the two already listed.** No translations, hacks, or bad dumps.
- ❌ **Do not put reference hacks in `base_game_roms/`.** They go in `reference/`.
- ❌ **Do not commit ROM files.** `.gitignore` blocks `*.smc`/`*.sfc`; do not bypass it.
- ❌ **Do not run `rm` on the ROM or project files** without explicit user confirmation.
- ❌ **Do not use `Legend of Pervert` or any text‑hack ROMs** as references — they are irrelevant to this project.
- ❌ **Do not build on Hyrule Magic, ZScream, or Black Magic.** They are useful as domain references only:
  - *Hyrule Magic* modifies the ROM on open, cannot expand it, and its tile edits are not reversible by the tool — building on it means inheriting silent corruption.
  - *ZScream* is still a ROM‑in‑place editor with known crash bugs on heavily edited ROMs and no clean intermediate representation.
  - *Black Magic* was never finished; key save paths are broken or absent.
  
  Concretely: do not use their internal data formats as the project schema, do not shell out to them as a write backend, and do not treat their limits as ROM limits. Constraints come from the disassembly and hardware, not from legacy editor behavior.
- ❌ **Do not assume YAZE's GUI save paths are correct** — they are still in flux as of v0.8.0. Verify against the disassembly.
- **Keep the roadmap honest.** Preserve phase ordering unless the user asks to change it, and update implementation status and affected docs whenever work lands.

---

## 10. Open Decisions and Local Verification Gates

- [x] Project data format → **SQLite canonical + JSON export** (ADR 0001); the current SQLite schema still stores project metadata only.
- [x] Disassembly submodule configured and source exports use revision `347c23f9fc019c72d32da537c9cb235f468d021d`; source-only inventories have parser-parity tests.
- [ ] Verify a trusted clean US ROM locally, including its header status and SHA-256. The ROM is user-supplied and intentionally absent from Git/CI.
- [ ] Smoke-test YAZE/`z3ed` against that local ROM and record exactly which read operations succeed.
- [ ] Choose the YAZE adapter strategy after the CLI smoke test (proposal: subprocess adapter).
- [ ] Test `z3cli` with the intended model endpoint or decide on a thin custom MCP server.
- [ ] Select and verify a headless emulator smoke-test path before any ROM writer is introduced.

---

## 11. Pointers

- **`ROADMAP.md`** — the phased plan. Read this before proposing new work.
- **`RESEARCH.md`** — the catalog of tools and projects referenced above, with more detail.
- **`docs/api.md`** — current documented API surface; extend it as CLI and authoring functions change.
- **`docs/schemas/`** — source-export contracts and discovery notes; full editable game-system schemas remain incomplete.
- **`docs/decisions/`** — Architecture Decision Records. Read `0001` before touching the data model.
- **`docs/glossary.md`** — terminology (IPS, ASM, MSU‑1, rooms vs. maps, etc.).
- **`README.md`** — human‑facing quickstart.

---

*Last updated: Day 0 of project. Update this file when conventions change, not when individual tasks complete.*
```
