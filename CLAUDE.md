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

**Intended US base ROM location (local-only; not yet verified):**

```
base_game_roms/Legend of Zelda, The - A Link to the Past (U) [!].smc
```

- This is the expected path for an authorized clean US dump used by future ROM-dependent tooling. The repository does not establish that the file is present, canonical, headerless, or otherwise valid.
- Repository setup and CI do not fetch, include, open, or modify a ROM. A size check is diagnostic, not proof of dump provenance or correctness.
- Before relying on a local ROM, run `just doctor` and `zelda-suite inspect-rom PATH`, then follow the staged read-only checks in [`docs/real-rom-verification.md`](./docs/real-rom-verification.md), including the scalar-table, overworld hidden-item, and dungeon-room pointer verifiers. Use `zelda-suite inspect-overworld-hidden-items` for a source-only layout report that does not open a ROM; `verify-overworld-hidden-items` performs the separate local-byte comparison. Byte agreement validates only the checked offsets; it does not establish ROM provenance. See [`docs/doctor.md`](./docs/doctor.md) and [`docs/rom-image-inspection.md`](./docs/rom-image-inspection.md).

**Optional JP reference (local-only; not read by current tooling):**

```
base_game_roms/Zelda no Densetsu - Kamigami no Triforce (J) (V1.0).smc
```

- This path is reserved for an authorized local reference dump if needed for later comparison. The file may be absent; no current build or CI workflow requires it.

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
| **YAZE / `z3ed`** | Candidate low‑level ROM interface (CLI + GUI) | Intended for overworld/dungeon/graphics/palette/message access. Its behavior has not yet been smoke-tested against a locally verified ROM; wrap future integration behind an adapter. |
| **`z3cli`** | Candidate agent harness (MCP, session management, model routing) | Proposed for Phase 3 workflows. Endpoint compatibility and a real tool call remain unverified. |
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
├── CONTRIBUTING.md
├── CHANGELOG.md
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
│   ├── project/store.py            ← SQLite project metadata + source-export snapshots
│   └── diff/rom_diff.py            ← file-backed ROM byte diff
├── tests/                          ← parser, export, CLI, project, and diff regression tests
└── docs/
    ├── api.md
    ├── project-format.md
    ├── project-assets.md
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

1. **No ROM writer exists yet.** Before adding ROM writes, implement an isolated `src/zelda_suite/write/` layer with bounds/reference checks, deterministic dry-run and byte-diff output, and a passing emulator smoke test (YAZE headless or equivalent). Never write a ROM until all gates pass.
2. **Cite your source.** Any proposed change must reference (a) the project data file/row and (b) the disassembly label / byte range in `AsarUSALTTPDisassembly`.
3. **Dry‑run first.** The authoring API must support a `dry_run=True` mode that reports intended changes without applying them. Default to dry‑run.
4. **Referential integrity.** A chest cannot point to a nonexistent item. An entrance cannot point to a nonexistent room. Enforce at the SQLite schema and the API layer, not the byte layer.
5. **Adapters, not dependencies.** Future YAZE, SpriteSomething, and zcompress integrations should be wrapped behind `src/zelda_suite/adapters/`. This adapter layer is a design rule, not a claim that those integrations already exist.
6. **The data model is the source of truth.** The ROM is a future build artifact. Current raw ROM reads belong in `src/zelda_suite/extract/`; do not introduce raw reads elsewhere. A future writer must be isolated under `src/zelda_suite/write/`.
7. **No legacy GUI tool assumptions.** Do not assume Hyrule Magic quirks are correct behavior. Trust the disassembly.

---

## 8. Workflow Conventions

- **One change = one commit.** The ROM diff goes in the commit body when the change affects ROM bytes.
- **Short-lived branches only.** Start each focused change from current `main`. Inspect unique commits before reusing any old branch; ahead/behind counts alone do not make a branch safe to merge. Never merge an old, diverged feature branch wholesale just to recover one missing change. GitHub's delete-branch-on-merge setting is enabled, so branches for merged PRs should be removed automatically.
- **Tests first for extraction logic.** Add a fixture before writing a parser.
- **Phase discipline.** Use `ROADMAP.md` as the current status ledger. Do not claim a phase exit criterion is met until implementation and evidence exist; label local-ROM or external-tool checks unverified when they have not been run.
- **Ask before adding dependencies.** Prefer stdlib and one well‑known library over a framework.
- **Log everything in `docs/`.** New schemas, new API functions, new ROM caveats.
- **Task runner:** `justfile` at repo root. Run `just` to list commands. `just doctor` is a local environment diagnostic, not a ROM-independent CI check: it exits nonzero when the expected US ROM is missing or incorrectly sized. It only checks tool executables on `PATH`; it does not prove the tools can read the ROM.

---

## 9. What NOT To Do

- ❌ **Do not commit ROM files.** The US base path and optional JP reference path above are local-only candidates; the JP file may be absent. Do not add translations, hacks, bad dumps, or other regional variants, and do not bypass the Git ignore rules.
- ❌ **Do not put reference hacks in `base_game_roms/`.** They go in `reference/`.
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

- [x] Project data format → **SQLite canonical + JSON export** (ADR 0001); schema v2 persists validated source-export snapshots with provenance and SHA-256. Editable game-system tables remain future work.
- [x] Disassembly submodule configured and source exports use revision `347c23f9fc019c72d32da537c9cb235f468d021d`; source-only inventories have parser-parity tests.
- [ ] Verify a trusted clean US ROM locally, including its header status and SHA-256. The ROM is user-supplied and intentionally absent from Git/CI.
- [ ] Smoke-test YAZE/`z3ed` against that local ROM and record exactly which read operations succeed.
- [ ] Choose the YAZE adapter strategy after the CLI smoke test (proposal: subprocess adapter).
- [ ] Test `z3cli` with the intended model endpoint or decide on a thin custom MCP server.
- [ ] Select and verify a headless emulator smoke-test path before any ROM writer is introduced.

---

## 11. Pointers

- **`ROADMAP.md`** — the phased plan. Read this before proposing new work.
- **`CONTRIBUTING.md`** — source inventory, test, registry, documentation, and ROM-verification workflow. Follow this when adding extractors or metadata assets.
- **`CHANGELOG.md`** and **`docs/versioning.md`** — record unreleased changes and keep package, project JSON, SQLite schema, registry, and source-export versions distinct.
- **`RESEARCH.md`** — the catalog of tools and projects referenced above, with more detail.
- **`docs/api.md`** — current documented API surface; extend it as CLI and authoring functions change. Use `zelda-suite audit-unresolved-table-expressions` to inventory unresolved registered scalar-table expressions without requiring a ROM or evaluating assembler syntax.
- **`docs/schemas/`** — source-export contracts and discovery notes; full editable game-system schemas remain incomplete.
- **`docs/decisions/`** — Architecture Decision Records. Read `0001` before touching the data model.
- **`docs/glossary.md`** — terminology (IPS, ASM, MSU‑1, rooms vs. maps, etc.).
- **`docs/schemas/overworld.md`** — overworld source discovery and High/Low pair validator.
- **`docs/schemas/dungeons.md`** — source-only 320-entry room pointer inventory and 266-entry room payload inventories across Bank03, Bank0A, and Bank1F; neither resolves target offsets or confirms playable-room count.
- **`docs/extracted-data.md`** — committed source inventory catalog and reproduction commands.
- **`docs/asset-loader.md`** and **`docs/incbin-inventory.md`** — source-export loader and inventory contracts. Use `zelda-suite audit-incbin-inventory` to summarize metadata gaps, range/size mismatches, and candidate span overlaps without opening payloads or a ROM.
- **`docs/project-assets.md`** — importing, querying, and validating source-export snapshots in SQLite projects. Use `import-extracted-asset` for committed registry assets so manifest provenance checks run before storage.
- **`README.md`** — human-facing quickstart and capability summary.

---

*Update these instructions when architecture, constraints, or workflow conventions change. Track task completion in `ROADMAP.md`; do not substitute assumptions for verification.*
```

When changing the text dictionary exports, run `zelda-suite audit-text-dictionary`; its committed-data cross-check is source-only and must preserve the `.You` extent discrepancy until the source and local-ROM evidence establish which annotation is correct.

When changing the registered text-message index, run `zelda-suite audit-text-message-index` and preserve the offset-comment and block-size warnings unless independently verified source/ROM evidence justifies changing source facts. The report is source-only; it is not a message decoder or ROM verification.

When changing registered music data, run `zelda-suite audit-music-assets`. It joins only the symbolic pointer index and the source `incbin` inventory, preserving the unmatched `Song0B_FairyTheme` target and the three missing size annotations without claiming anything about ROM payload availability.
