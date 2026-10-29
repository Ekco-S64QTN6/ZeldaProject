# `zelda-suite doctor`

Run `just doctor` (or `uv run zelda-suite doctor`) from the repository
workspace. Use `--workspace PATH` to inspect a different workspace root.

The command checks:

- The canonical US ROM exists at
  `base_game_roms/Legend of Zelda, The - A Link to the Past (U) [!].smc`.
- The ROM file is exactly 1,048,576 bytes, the expected headerless size. A
  1,049,088-byte file is reported as likely containing a 512-byte copier header.
- The `z3ed` and `z3cli` executables are visible on `PATH`.

A missing or incorrectly sized ROM makes the command exit with status 1.
Missing tools are warnings so the command remains useful while the environment
is being set up. Tool checks only look for executables: they do not invoke
YAZE/z3ed or z3cli and do not claim that either can successfully parse the ROM.

The ROM check uses filesystem metadata only; it does not read or modify ROM
bytes. Keep ROMs local and never commit them.

For a staged local-ROM workflow, including a self-diff smoke test, a read-only
cross-check of selected source-annotated table bytes, and the current partial
YAZE v0.7.2 capability results, see
[`real-rom-verification.md`](./real-rom-verification.md).

Environment note (2026-10-29): `z3ed` was extracted under
`$HOME/.local/opt/yaze-0.7.2/yaze-0.7.2-Linux/z3ed` and run by absolute path,
not added to `PATH`; `doctor` therefore correctly continued to report its PATH
warning. `z3cli` was not installed/on `PATH`. The tested YAZE commands and the
remaining overworld map-read failure are documented in the runbook.
