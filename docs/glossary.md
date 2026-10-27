# Glossary

- **ALttP** — *The Legend of Zelda: A Link to the Past* (SNES, 1991).
- **Base ROM** — the clean US dump
  `Legend of Zelda, The - A Link to the Past (U) [!].smc`. Headerless.
- **ROM** — the SNES binary. **Never** edit by hand in this project; go through
  the authoring API.
- **Project file** — the SQLite/JSON representation of a work‑in‑progress hack.
  See ADR 0001.
- **Hack / romhack** — a modified ROM distributed as an IPS patch (or occasionally
  a full ROM).
- **IPS** — International Patching System. The de‑facto format for distributing
  ALttP hacks. Applied to a clean base ROM.
- **ASM** — 65816 assembly; used for custom code (menu logic, HUD, MSU‑1, etc.).
- **Asar** — the modern 65816 assembler used by the community.
- **Disassembly** — `AsarUSALTTPDisassembly`, the full source‑level view of the
  ROM. **Ground truth.**
- **Room** — a dungeon screen (one 512×512 tile grid, or a subset).
- **Overworld map** — one of 160 screens on the Light/Dark World overworld.
- **Chest table** — the table mapping dungeon chests to items.
- **MSU‑1** — a coprocessor mod that adds CD‑quality audio and extra storage.
  qwertymodo's ASM patch brings it to ALttP.
- **Parallel Worlds** — Euclid/SePH/Con/qwertymodo/PuzzleDude's 2004 hack, and
  the project's design lineage reference.
- **CHRT** — *Conker's High Rule Tail*, the spiritual successor to Parallel
  Worlds and the model for the kind of hack this suite should enable.
