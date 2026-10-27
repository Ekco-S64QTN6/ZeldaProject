# ADR 0001 — Project data format

- **Status:** Proposed
- **Date:** Day 0
- **Deciders:** ekco

## Context

The suite needs a canonical, editable representation of an ALttP ROM that:

1. Is human‑readable enough to review in git diffs.
2. Is queryable enough that Claude can ask "which chests are in dungeon 3?"
   without loading the whole file.
3. Survives round‑trips (`extract → edit → write`) without drift.

Candidates considered: raw JSON, YAML, TOML, SQLite, a custom binary.

## Decision

**SQLite** as the canonical project file (`project/<name>.db`), with a
**JSON export** (`project/<name>.json`) generated on every save for git diffs.

Rationale:

- SQLite handles the referential‑integrity requirement directly (foreign keys,
  `CHECK` constraints) — this is the "a chest cannot point to a nonexistent
  item" rule from CLAUDE.md, enforced at the storage layer.
- Query performance matters once we have ~300 dungeon rooms × ~50 objects each.
- JSON export keeps git history reviewable without requiring reviewers to run
  `sqlite3` on the binary.
- YAML/TOML get unwieldy fast at this table count; raw JSON loses the
  constraint enforcement.

## Consequences

- Every authoring API call must round‑trip through SQLite.
- Schema migrations become a thing. Plan a `project.schema_version` table from
  day one.
- A JSON export diff will be noisy until we canonicalize key order and float
  formatting. Do that in the export module from the start.

## Alternatives not chosen

- **Pure JSON**: rejected because referential integrity has to be re‑enforced in
  every code path that mutates the model.
- **Pure YAML**: rejected — too slow to query, too easy to hand‑edit into an
  invalid state.
- **Custom binary**: rejected — unreadable in git diffs; kills review.
