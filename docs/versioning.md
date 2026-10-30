# Versioning and compatibility policy

ZeldaProject has several independent version numbers. They describe different
contracts and must not be treated as interchangeable.

## Version domains

| Version | Current owner | What it versions | When to increment |
| --- | --- | --- | --- |
| Python package | `pyproject.toml` → `[project].version` | The installable `zelda-suite` code and CLI | Use SemVer-style `MAJOR.MINOR.PATCH` once release tags are introduced. Before 1.0, keep `0.y.z`: increment the patch for fixes or documentation changes that preserve public contracts, and increment the middle component for new public features or public API/CLI compatibility changes. Reserve `1.0.0` for the first release that intends to offer a stable public contract. |
| Project JSON format | `PROJECT_FORMAT_VERSION` in `src/zelda_suite/project/store.py` | The top-level `zelda-suite-project` JSON sidecar shape and meaning | Increment when the serialized project envelope or interpretation changes incompatibly. Add or update compatibility tests and document what older readers can handle. |
| SQLite schema | `CURRENT_SCHEMA_VERSION` in `src/zelda_suite/project/store.py` | Tables, columns, constraints, and stored database invariants | Increment whenever the physical schema or required stored invariants change. Add an explicit migration for each supported prior version and test it on a fixture of that version. |
| Individual source export | Each export's `format` and `format_version` | One parser/metadata JSON contract, e.g. `zelda-suite-data-table` | Version each export format independently. A changed key set, required field, field meaning, or normalization that affects consumers requires a version increment and a corresponding schema/validator/test update. |
| Asset registry | `format_version` in `data/extracted/manifest.json` | Registry envelope and per-asset metadata fields | Increment if the registry's serialized contract changes; update the registry schema, validator, tests, and docs together. |

The project JSON format and SQLite schema versions are deliberately separate.
A new database table can require a schema migration without requiring a JSON
envelope change; a changed JSON export can require a project-format increment
even if SQLite's physical tables do not change. If both contracts change, bump
both and test both paths.

## Source-export compatibility

The loader uses strict, format-specific key and invariant checks. Do not add
fields to a version-1 record and continue labelling it version 1: an older
strict reader may reject the new field, and a reader cannot know the field's
meaning from its name alone. Instead, add an explicit version and maintain the
older validator when old files must remain usable.

For example, `zelda-suite-data-table` v1 omits inline comments. The opt-in
`inspect-data-table --include-comments` path emits v2 with a required
`inline_comment` value per entry (a string or null). The default remains v1,
and the two schemas live separately at
[`data-table-export.schema.json`](./schemas/data-table-export.schema.json) and
[`data-table-export-v2.schema.json`](./schemas/data-table-export-v2.schema.json).

A change to a source revision or record count is provenance/data refresh, not
automatically a format-version change. Update the registered asset file,
revision, count, parser-parity tests, and reproduction docs; bump its format
only if its serialization contract or semantics changed. Likewise, changing a
source comment or computed offset does not by itself prove that a format change
is appropriate.

## Release and changelog process

1. Every behavior, API/CLI, project schema, registry, or export-format change
   updates [`CHANGELOG.md`](../CHANGELOG.md) under `[Unreleased]`.
2. Before a release, review the unreleased entries, verify the chosen package
   version, and confirm that all required format/schema migrations and backward
   compatibility tests are present.
3. Tag the package release as `vMAJOR.MINOR.PATCH` and publish release notes
   from the changelog. Never label an unreleased development snapshot as a
   formal release.
4. Keep the package version, project JSON format version, SQLite schema
   version, registry version, and source-export versions explicit in release
   notes whenever they change.

The package currently declares version `0.3.0` in `pyproject.toml`. That value
is not evidence of a published release. The versioned-format rules in this
document are policy; a formal release/tag workflow still needs to be exercised
before claiming release automation is complete.
