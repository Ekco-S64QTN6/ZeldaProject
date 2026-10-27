Project: Claude‑Driven RPG Maker‑Style Suite for ALttP ROM Hacking

Base ROM: Legend of Zelda, The - A Link to the Past (U) [!].smc (clean US release, no header)
Goal: Replace fragile, GUI‑bound legacy editors with a scriptable, AI‑native pipeline that lets Claude (or any agent) parse, edit, and rebuild a Zelda 3 ROM as structured project data.
Phase 0 — Foundation (Current)

Objective: Establish the canonical ROM, workspace layout, and low‑level access primitives.

    □

    Confirm the clean US ROM is the only .smc in the workspace.
    □

    Verify ROM header state (512‑byte header vs. headerless). Document the exact offset map for early debugging.
    □

    Install and smoke‑test YAZE / z3ed as the reference CLI for ROM operations. Confirm it can parse the US ROM and dump basic structures (overworld maps, dungeon rooms, message tables).
    □

    Install z3cli in a separate Python environment. Validate that it can attach to the ROM and run a trivial tool call (e.g., list dungeon rooms or read a chest table).
    □

    Decide on a project‑file format (JSON / YAML / SQLite) to hold extracted, human‑readable game data between Claude sessions.

Exit criteria: A single project/ directory containing the clean ROM, a .gitignored workspace for generated assets, and proof that both z3ed and z3cli can read the ROM without errors.
Phase 1 — Structured Extraction

Objective: Convert opaque ROM bytes into a complete, queryable data model that Claude can reason about.

    □

    Use YAZE’s CLI (z3ed) to dump the overworld map table (160 maps), dungeon room table (296 rooms), and core graphics/palette sheets.
    □

    Cross‑reference the AsarUSALTTPDisassembly for exact labels, table addresses, and data‑structure definitions that the GUI tools abstract away.
    □

    Extract message/dialogue data, item tables, sprite definitions, and music track pointers into the project format.
    □

    Build a lightweight Python/Node “asset loader” library that Claude can call to read or validate any extracted table by name.
    □

    Write a ROM diff harness: given a modified project file, produce a deterministic byte‑level diff against the base ROM so every edit is auditable.

Exit criteria: Every major game system (overworld, dungeons, text, items, sprites, audio) has a corresponding extracted data file and a loader function. No raw hex editing is required to inspect the game.
Phase 2 — Editor Core & Authoring API

Objective: Give Claude a stable, semantic API for making changes, and give the human a usable GUI shell.

    □

    Expose a CRUD API over the project data model: createRoom, updateChestItem, setOverworldTile, moveEntrance, etc.
    □

    Map each API call to the correct ROM write via YAZE’s scripting layer or a direct binary writer validated against the disassembly.
    □

    Implement guardrails: bounds checks, referential integrity (e.g., a chest cannot point to a nonexistent item), and a dry‑run mode that reports what would change.
    □

    Build a minimal web UI (or extend YAZE’s ImGui frontend) that calls the same API, so human edits and Claude edits go through identical paths.
    □

    Integrate SpriteSomething’s ZSPR handling for sprite import/export and zcompress compatibility for graphics decompression/recompression.

Exit criteria: A user can open a project file in the UI, change a room or chest, save, and reproduce the same edit by asking Claude to call the equivalent API function.
Phase 3 — Claude Integration & Agent Workflows

Objective: Make Claude a first‑class collaborator, not a prompt‑and‑pray wrapper.

    □

    Wrap the authoring API as MCP tools so Claude can call list_dungeon_rooms, inspect_room(0x42), place_enemy, etc., with structured responses.
    □

    Use z3cli as the agent harness for model routing, session persistence, and tool‑call review.
    □

    Define a project reference protocol: Claude must cite the extracted data file and byte range for every proposed change.
    □

    Implement a verification loop: after Claude writes a change, automatically run the ROM diff harness and a lightweight emulator smoke test (YAZE’s built‑in emulator or a headless SNES core).
    □

    Build example agent tasks: “Create a three‑room dungeon with a key‑locked boss door,” “Rebalance all chest contents in dungeon 3,” “Translate all signs to a custom language.”

Exit criteria: At least three nontrivial editing tasks can be completed by Claude from a natural‑language prompt, with each change traceable to a specific API call and ROM diff.
Phase 4 — Maker‑Style Expansion

Objective: Move beyond editing individual rooms toward assembling full games or large‑scale conversions.

    □

    Study Zelda Reloaded Maker’s project‑file paradigm (build from scratch, not patch‑on‑top) and decide which concepts transfer to ALttP.
    □

    Add project‑level templates: “vanilla‑like overworld,” “dungeon‑crawl,” “puzzle‑heavy,” etc., that pre‑populate the data model.
    □

    Implement bulk operations: regenerate all overworld maps from a higher‑level map description, auto‑place entrances/exits based on graph connectivity.
    □

    Add export/publish tooling: IPS patch generation (using Lunar IPS or a pure‑Python patcher), readme generation, and versioned release artifacts.
    □

    Evaluate Solarus or Z3R as optional export targets if the user wants a non‑SNES runtime.

Exit criteria: A user can start from a template, make broad structural changes, and produce a distributable patch without manually editing individual bytes or rooms unless desired.
Phase 5 — Hardening & Distribution

Objective: Make the suite reliable enough for non‑expert users and maintainable long‑term.

    □

    Add automated regression tests: edit a fixture project, rebuild, and compare against a golden ROM hash.
    □

    Document every API function, every extracted data schema, and every known ROM caveat.
    □

    Provide a one‑command installer that pulls the base ROM, sets up YAZE/z3cli, and initializes a project.
    □

    Establish a changelog and semantic versioning for the project‑file format.
    □

    Write contributor guidelines for extending the API or adding new extraction modules.

Risks & Mitigations
Risk	Mitigation
YAZE/z3cli are young projects; APIs may change	Pin versions, wrap external CLIs behind a thin adapter layer, keep extraction logic independent.
ROM writes corrupt game data silently	Always validate against disassembly labels; require a diff + emulator smoke test before accepting a change.
Claude hallucinates tool calls or data references	MCP tool schemas must reject malformed inputs; every change must cite the source data file and byte range.
Over‑reliance on GUI editor quirks	Treat the disassembly and extracted data as ground truth; the GUI is a view, not the source of truth.
