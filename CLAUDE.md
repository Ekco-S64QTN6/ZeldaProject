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
├── base_game_roms/              ← ROMs (gitignored except README)
│   ├── README.md
│   ├── Legend of Zelda, The - A Link to the Past (U) [!].smc   (untracked)
│   └── Zelda no Densetsu - Kamigami no Triforce (J) (V1.0).smc (untracked)
├── reference/                   ← read-only reference material
│   ├── README.md
│   ├── AsarUSALTTPDisassembly/  ← git submodule
│   └── parallel_worlds/
│       ├── List of Updates for v1.23 (for romhackers only).txt
│       ├── Parallel Worlds Team.md
│       ├── Zelda3_Parallel_Worlds_v1-23.ips
│       ├── Zelda3_Parallel_Worlds_v1-23.smc     (untracked)
│       └── zpw-v1.23_ReadMe.txt
├── src/zelda_suite/
│   ├── extract/                 ← ROM → project data
│   ├── author/                  ← CRUD API over project data
│   ├── write/                   ← project data → ROM bytes
│   ├── diff/                    ← ROM diff harness
│   ├── adapters/                ← thin wrappers: yaze, sprite_something, zcompress
│   └── cli/                     ← user-facing entry points
├── project/                     ← working projects (gitignored)
│   └── .gitkeep
├── tests/
│   └── fixtures/
│       ├── README.md
│       └── local/               ← untracked, gitignored
└── docs/
    ├── api.md
    ├── glossary.md
    ├── schemas/
    └── decisions/
        └── 0001-project-data-format.md
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
- **Phase discipline.** Do not skip ahead to Phase 3 (agent integration) before Phase 2 (authoring API) is solid. Each phase in `ROADMAP.md` has explicit exit criteria.
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
- ❌ **Do not propose changes to Claude's own context or the ROADMAP phases** without asking.

---

## 10. Open Decisions (Phase 0 Must Resolve)

- [x] Project data format → **SQLite canonical + JSON export** (ADR 0001, proposed).
- [ ] Adapter strategy for YAZE: subprocess CLI vs FFI vs reimplementation. (Proposal: subprocess `z3ed` CLI, wrap in Python.)
- [ ] Agent harness: `z3cli` vs custom MCP server. (Proposal: try `z3cli` first; fall back to a thin MCP wrapper if endpoint compatibility fails.)
- [ ] Emulator smoke test: YAZE headless vs `bsnes`/`snes9x` CLI. (Proposal: YAZE headless if stable; otherwise snes9x with a scripted input sequence.)
- [ ] `AsarUSALTTPDisassembly` integration: confirmed as git submodule at `reference/AsarUSALTTPDisassembly/`. Update `RESEARCH.md` when pinned.

---

## 11. Pointers

- **`ROADMAP.md`** — the phased plan. Read this before proposing new work.
- **`RESEARCH.md`** — the catalog of tools and projects referenced above, with more detail.
- **`docs/api.md`** — the authoring API surface (to be written in Phase 2).
- **`docs/schemas/`** — the project data schemas (to be written in Phase 1).
- **`docs/decisions/`** — Architecture Decision Records. Read `0001` before touching the data model.
- **`docs/glossary.md`** — terminology (IPS, ASM, MSU‑1, rooms vs. maps, etc.).
- **`README.md`** — human‑facing quickstart.

---

*Last updated: Day 0 of project. Update this file when conventions change, not when individual tasks complete.*
```
