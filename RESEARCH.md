Tools, Projects & Resources Relevant to a Claude‑Driven ALttP Hacking Suite

This document catalogs the ecosystem tools and projects that should inform or be integrated into the suite. Each entry notes what it does, its current state, and how it relates to the goal of a scriptable, RPG Maker‑style ALttP editing pipeline.
1. YAZE (Yet Another Zelda3 Editor) — scawful/yaze

What it is: A cross‑platform ROM editor for ALttP built in C++23 with ImGui. Includes a built‑in SNES emulator, the Asar 65816 assembler, and a CLI called z3ed explicitly designed for scripted ROM operations and AI‑agent integration.

Relevance: `z3ed` offers scripted ROM inspection commands for ROM metadata/raw bytes, dungeon rooms/sprites, graphics bytes, palette groups, and messages. In a user-run smoke test on 2026-10-29, the official v0.7.2 Linux release successfully performed these read-only operations against the project's locally supplied ROM. Treat the tested binary as a candidate low-level interface, not as an already integrated backend; keep it behind an adapter and validate its output against the disassembly and project model.

Caveats: the same v0.7.2 smoke test could not read overworld screen 80: `overworld-describe-map --screen=80` failed with `Offset 1311049 out of range (size: 1048576)`. A dungeon-room response also contained a malformed staircase label. A successful exit status is not sufficient to establish output correctness. No write/save/rebuild operations were tested. The repository's newer development line may differ from the tested release; consult the [local-ROM verification runbook](./docs/real-rom-verification.md) for the exact version, checksum, commands, and current limitations.
2. z3cli — scawful/z3cli

What it is: A “model‑first Zelda hacking CLI” designed to feel like a lightweight Claude Code session. Supports local LM Studio / llama.cpp models, MCP tool calling, resumable sessions, diff review, and a JSON‑RPC daemon mode.

Relevance: This is effectively the agent harness the project needs in Phase 3. Rather than building session management, tool permissions, and model routing from scratch, z3cli can serve as the backend that connects Claude (or a local model) to the authoring API. Its MCP support and @file attachment model align directly with the project’s goal of structured, auditable AI edits.

Caveats: It is explicitly experimental and oriented toward local models / LM Studio. As of the user's 2026-10-29 environment check, `z3cli` was not on `PATH` and no model-endpoint tool call had been tested. Verify that it can route to Claude via an Anthropic-compatible endpoint before committing to it as the sole harness.
3. Super Zelda Editor — Derek McPherson / DMCP2143

What it is: A complete ALttP game editor based on Hyrule Magic, with bug fixes and new features. Notably supports expanded 2 MB ROMs, a full dungeon‑room visualization mode showing all layers and invisible objects, prefab room segments, and a three‑sprite‑per‑overworld‑tile capacity.

Relevance: The expanded‑ROM support and room visualization techniques are directly applicable if the suite ever moves beyond vanilla ROM size. Its approach to prefab rooms and multi‑layer object visibility is worth studying for the editor core in Phase 2, even if the suite does not reuse its code directly.
4. Zelda Reloaded Maker — MetalMachine

What it is: A “maker” (not a ROM editor) for Zelda 1 (NES). It builds a full game from a project file, with editable overworlds, dungeons, enemies, items, music, and a custom overworld engine. It explicitly distinguishes itself from a patcher: it generates a new expanded ROM from project data.

Relevance: This is the conceptual model for the “RPG Maker‑style” layer in Phase 4. Even though it targets NES Zelda 1, its project‑file architecture, independent enemy lists, and non‑Euclidean screen connections are useful reference designs for a higher‑level ALttP authoring experience. Do not expect to reuse its code, but study its data model.
5. Solarus Engine

What it is: An open‑source Action‑RPG engine specifically designed for Zelda‑style games, often described as an alternative to RPG Maker XP for the ARPG genre. It supports custom assets, Lua scripting, and full game creation from scratch.

Relevance: If the project ever wants an export target that is not a SNES ROM (e.g., a modern standalone game), Solarus is a natural candidate. It is not a ROM editor, but it can consume extracted assets and provide a playable runtime for projects that outgrow the SNES constraints.
6. SpriteSomething — Artheau/SpriteSomething

What it is: A Python tool for extracting, editing, and injecting sprites in ALttP and several romhacks/randomizers. Supports ZSPR format, PNG import/export, animation export, and a command‑line interface.

Relevance: Directly useful for the sprite/authoring pipeline. Its ZSPR handling and CLI mode can be wrapped as an authoring API tool, and its support for randomizer sprite formats means it is already designed to work with modified ROMs rather than only vanilla.
7. Z3R (Zelda 3 Reborn) — xander-haj/Z3R

What it is: A fork of the zelda3 C reimplementation of ALttP by SnesRev. It builds a native executable and a generated asset file (zelda3_assets.dat) from the user’s ROM. Includes widescreen, HUD, settings, and early randomizer work, with a Python‑based asset extraction workflow (restool.py) and YAML‑backed data.

Relevance: Z3R demonstrates a clean extract‑to‑YAML → edit → rebuild‑assets pipeline, which is almost exactly the data model the suite needs in Phase 1–2. Its restool.py extraction approach and YAML data representation are worth studying as a reference architecture, even if the suite targets the SNES binary rather than the C reimplementation. It also provides an alternative runtime/export target.
8. AsarUSALTTPDisassembly — JaredBrian/AsarUSALTTPDisassembly

What it is: A work‑in‑progress full US disassembly of ALttP made to work with the Asar SNES assembler.

Relevance: The single most important ground‑truth resource for ROM semantics. Any byte‑level write performed by the suite should be validated against labels and table definitions from this disassembly. It is also the best reference for understanding which regions of the ROM are safe to relocate or expand.
9. Legacy Tools (Still Worth Knowing)

These are not primary building blocks, but they define the ecosystem’s conventions and are often referenced in hack documentation.

    Hyrule Magic: The original ALttP editor. Still used for overworld, dungeon, music, and text editing in major hacks like Parallel Worlds, but fragile and not scriptable.

    ZScream: A successor/alternative editor used alongside Hyrule Magic in Parallel Worlds; useful as a comparison for UI conventions.

    zcompress: The standard Zelda 3 graphics compression/decompression tool; still the reference for graphics round‑tripping.

    YY‑CHR: A general‑purpose tile editor commonly used for ALttP graphics after decompression.

    Lunar IPS: The de facto IPS patching utility; relevant for Phase 4 release tooling.

    HxD / Windhex: Hex editors. Useful for ad‑hoc debugging but should not be part of the automated pipeline.

10. Related Projects & Communities

    ALttP Randomizer (alttpr ecosystem): The randomizer community has produced extensive tooling for reading and rewriting ALttP item/entrance/chest tables. Projects like codemann8/ALttPDoorRandomizer and the alttp_vt_randomizer provide working examples of programmatic ROM modification at scale.

    Mudora (blog.ty-porter.dev): A Go tool for analyzing randomized ALttP ROMs even when encrypted. Its approach to parsing ROM state programmatically is relevant to the verification harness in Phase 3.

    Archipelago Multi‑Game Randomizer: While broader in scope, its ALttP integration demonstrates how to expose ALttP game data as a structured, remote‑callable service.

Summary Recommendation

For the immediate next steps, investigate the known v0.7.2 screen-80 map-read failure and malformed room label before designing a YAZE adapter; test z3cli with the intended model endpoint; and continue to use AsarUSALTTPDisassembly as the semantic ground truth. Study Z3R’s YAML asset pipeline for the data‑model design, and keep SpriteSomething and zcompress in mind for graphics/sprite round‑tripping. The legacy GUI editors (Hyrule Magic, ZScream, Super Zelda Editor) are useful as domain references but should not be treated as dependencies for a Claude‑native workflow.
