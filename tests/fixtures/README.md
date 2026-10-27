# Test fixtures

Two kinds of fixtures:

- **Committed:** golden hashes (`*.sha256`), expected JSON exports, sample
  project files. These must be reproducible from a clean base ROM.
- **Local, untracked:** extracted ROM slices, generated reference output.
  Stored under `tests/fixtures/local/` and gitignored.

Never commit an actual ROM file, even a partial one.
