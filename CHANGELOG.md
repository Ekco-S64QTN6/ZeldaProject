# Changelog

Changes that have landed on `main` but have not been included in a published
release are recorded under **Unreleased**. No numbered release history is
listed here yet; this file starts tracking the current development state and
does not imply that any release has been published.

## [Unreleased]

### Added

- A staged, read-only local-ROM verification runbook covering file inspection,
  self-diff smoke testing, selected source-table byte comparisons, and
  external-tool capability checks.
- Source-derived, manifest-registered metadata inventories for the currently
  covered falling-prize, text, sprite dispatch, music, overworld, receive-item,
  and dungeon room-pointer/payload declarations. Source annotations and
  unresolved values remain explicit; ROM bytes and binary `incbin` payloads
  are not committed.
- Read-only consistency checks for overworld High/Low payload pairs, dungeon
  pointer targets versus the union of all three room payload inventories, and
  the music pointer/payload label relationship.
- SQLite project schema v2 for importing validated source-export snapshots,
  with explicit v1-to-v2 migration, duplicate-key protection, source
  provenance, canonical JSON exports, and SHA-256 integrity checks.
- Manifest-backed project asset import by name, with registry format, source
  revision, filename, and record-count validation before persistence.
- Opt-in `zelda-suite inspect-data-table --include-comments` export format v2,
  preserving per-line inline comments while keeping the default version-1
  output contract unchanged.
- `CONTRIBUTING.md` plus this changelog and the versioning policy.
- Cross-platform workspace setup scripts (`scripts/setup.sh` and
  `scripts/setup.ps1`) that prepare dependencies, initialize and validate a
  project, and never fetch or modify ROMs.

### Changed

- Reconciled `ROADMAP.md`, `README.md`, `CLAUDE.md`, and subsystem
  documentation with the implemented parser, registry, project-store, and
  source-inventory capabilities. Local-ROM checks now include a user-run
  byte comparison that matched all five falling-prize arrays at source-
  annotated offsets; canonical ROM provenance and external-tool verification
  remain open.
- Clarified that the documented US ROM path is only a local setup convention,
  not proof that a dump exists or is valid; made the agent instructions and
  human-facing quickstart consistent with the still-open ROM/tool verification
  gates.
- Reconciled the hidden-item source region's byte accounting with the pinned
  reader's three-byte stride and `$FFFF` termination. Local-ROM verification
  and per-area grouping remain open.
- Documented the seven-entry falling-prize lookup as a joined source-only view
  over its five parallel arrays, while preserving the open local-ROM byte
  verification gate.
- Corrected the fixture-directory guide to match the actual tracked files and
  clarify that ROM images, ROM slices, and golden ROM artifacts are not
  committed or required by ROM-independent tests.

### Verification

- Added and expanded parser-parity, export-validation, project migration,
  registered-asset round-trip, dungeon-label cross-reference, music-label
  cross-reference, overworld pair-integrity, source-comment, setup fallback
  orchestration, falling-prize consumer, and hidden-item sentinel/accounting
  source tests.
- The main-branch CI suite checks Python syntax, Ruff across all Python files
  in `src` and `tests`, strict MyPy types for `src`, and the full pytest suite.
- Linux and Windows CI smoke tests execute the POSIX and PowerShell setup
  scripts respectively, create and validate SQLite/JSON project files in
  temporary workspaces, and do not require a ROM.
- CI builds the Python wheel, installs it into a clean virtual environment, and
  smoke-tests the installed CLI by initializing and validating a project.
