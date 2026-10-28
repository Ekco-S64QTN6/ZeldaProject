# Test fixtures

The current automated tests use synthetic data, source-derived JSON exports,
or temporary files created under pytest's per-test temporary directories.
There are no committed clean-ROM hashes, ROM slices, or golden ROM images in
this directory.

The `tests/fixtures/local/` directory is reserved for local, untracked
diagnostic material when needed. Keep ROMs, partial ROMs, extracted ROM bytes,
and generated outputs out of Git. Do not make a ROM a prerequisite for
ROM-independent unit tests or CI.
