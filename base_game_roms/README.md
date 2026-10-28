# Base game ROMs

This directory is **gitignored**. Place ROMs here, do not commit them.

Intended local input for future ROM-dependent verification:

- `Legend of Zelda, The - A Link to the Past (U) [!].smc` — expected path for an
  authorized clean US dump. The repository does not establish that a file is
  present here, that it is the canonical dump, or that it is headerless. The
  size check in `just doctor` is diagnostic only; it does not verify provenance
  or contents. See [`docs/doctor.md`](../docs/doctor.md),
  [`docs/rom-image-inspection.md`](../docs/rom-image-inspection.md), and the
  open verification gates in [`ROADMAP.md`](../ROADMAP.md).

Optional local reference:

- `Zelda no Densetsu - Kamigami no Triforce (J) (V1.0).smc` — Japanese original
  for potential future comparison. This file may be absent; current builds and
  CI do not require or read it.
