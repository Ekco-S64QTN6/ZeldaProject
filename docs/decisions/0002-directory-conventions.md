# ADR 0002 — Directory conventions

- **Status:** Accepted
- **Date:** Day 0

## Decision

Two distinct "reference" locations, never interchangeable:

- **`reference/`** (top level) — external read-only material: the
  `AsarUSALTTPDisassembly` submodule and the `parallel_worlds` artifacts.
- **`docs/references/`** — reserved for *our* documentation that cites
  external material (e.g. a future `docs/references/rom-offsets.md`). Not
  yet in use; may be left empty.

Do not create a `reference/README.md` inside `docs/` or vice versa.
