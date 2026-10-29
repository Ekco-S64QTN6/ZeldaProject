"""Entry point for the `zelda-suite` CLI."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import click

from zelda_suite import __version__
from zelda_suite.diff import compare_bytes
from zelda_suite.extract import (
    DATA_DIRECTIVE_WIDTHS,
    DICTIONARY_INVENTORY_FORMAT,
    MIXED_DATA_TABLE_FORMAT,
    PINNED_TEXT_SOURCE_REVISION,
    POINTER_DIRECTIVE_WIDTHS,
    AssetLoadError,
    DungeonChestDataAuditError,
    DungeonRoomAssetAuditError,
    DungeonRoomDoorPointerAuditError,
    IncbinInventoryAuditError,
    ItemReceiptAnnotationAuditError,
    MessageSourceBlock,
    MusicAssetAuditError,
    OAMAllocationAuditError,
    OverworldPayloadPairError,
    PaidOverworldInteractionsAuditError,
    PotionShopTransactionsAuditError,
    ROMImageInspectionError,
    ROMTableVerificationError,
    ShopItemHandlersAuditError,
    SourceExpressionAuditError,
    SpecialShopTransactionsAuditError,
    SpritePrepDispatchAuditError,
    TextDictionaryAuditError,
    TextDictionaryPointerVerificationError,
    TextMessageByteVerificationError,
    TextMessageIndexAuditError,
    audit_dungeon_chest_data,
    audit_dungeon_room_assets,
    audit_dungeon_room_door_pointer_bounds,
    audit_incbin_inventories,
    audit_item_receipt_annotations,
    audit_music_assets,
    audit_oam_allocation,
    audit_overworld_payload_layout,
    audit_paid_overworld_interactions,
    audit_potion_shop_transactions,
    audit_shop_item_handlers,
    audit_special_shop_transactions,
    audit_sprite_prep_dispatch,
    audit_text_dictionary_assets,
    audit_text_message_index,
    audit_unresolved_table_expressions,
    build_item_receipt_layout,
    inspect_rom_image,
    load_source_export,
    parse_data_table,
    parse_dictionary_fragment_inventory,
    parse_dungeon_chest_data,
    parse_incbin_inventory,
    parse_mixed_data_table,
    parse_music_track_index,
    parse_overworld_hidden_item_source,
    parse_paid_overworld_interactions,
    parse_potion_shop_transactions,
    parse_shop_item_handlers,
    parse_source_pointer_table,
    parse_special_shop_transactions,
    parse_sprite_dispatch_table,
    parse_sprite_prep_dispatch_table,
    parse_text_message_index,
    read_rom_bytes,
    sha256_rom_bytes,
    validate_overworld_payload_pairs,
    validate_source_export,
    verify_dungeon_room_pointers,
    verify_overworld_hidden_items,
    verify_registered_scalar_tables,
    verify_text_dictionary_pointers,
    verify_text_message_bytes,
)
from zelda_suite.project import (
    get_source_asset,
    import_extracted_asset,
    import_source_asset,
    initialize_project,
    list_source_assets,
    migrate_project,
    validate_project,
)
from zelda_suite.project.store import BASE_ROM_FILENAME

US_ROM_FILENAME = BASE_ROM_FILENAME
EXPECTED_US_ROM_SIZE = 1_048_576
COPIER_HEADER_SIZE = 512
SNES_ROM_BANK_SIZE = 0x8000

TOOL_CHECKS = (
    ("z3ed", "YAZE/z3ed CLI"),
    ("z3cli", "z3cli agent harness"),
)


def _inspect_base_rom(path: Path) -> tuple[str, str]:
    """Check the canonical ROM path and its expected headerless file size.

    This intentionally inspects filesystem metadata only; ROM bytes are read
    exclusively by future extraction/writing modules.
    """
    try:
        if not path.is_file():
            return "FAIL", f"not found: {path}"
        size = path.stat().st_size
    except OSError as exc:
        return "FAIL", f"could not inspect {path}: {exc}"

    if size == EXPECTED_US_ROM_SIZE:
        return "OK", f"headerless US ROM found ({size:,} bytes): {path}"

    if size == EXPECTED_US_ROM_SIZE + COPIER_HEADER_SIZE:
        return (
            "FAIL",
            (
                "ROM appears to include a 512-byte copier header "
                f"({size:,} bytes); expected a headerless file "
                f"({EXPECTED_US_ROM_SIZE:,} bytes)."
            ),
        )

    if size % SNES_ROM_BANK_SIZE == COPIER_HEADER_SIZE:
        return (
            "FAIL",
            (
                f"file size ({size:,} bytes) has a 512-byte copier-header offset; "
                "expected the clean, headerless US ROM."
            ),
        )

    return (
        "FAIL",
        (
            f"unexpected ROM size ({size:,} bytes); expected exactly "
            f"{EXPECTED_US_ROM_SIZE:,} bytes for the headerless US ROM."
        ),
    )


@click.group()
@click.version_option(__version__)
def cli() -> None:
    """ZeldaProject authoring suite."""





def _parse_offset_text(value: str) -> int:
    """Parse a decimal, 0x-prefixed, or Asar-style $-prefixed offset."""
    try:
        if value.startswith("$"):
            return int(value[1:], 16)
        if value.lower().startswith(("0x", "+0x", "-0x")):
            return int(value, 0)
        return int(value, 10)
    except ValueError as exc:
        raise click.BadParameter(
            "use a decimal, 0x-prefixed, or Asar-style $-prefixed integer"
        ) from exc


@cli.command(name="inspect-pointer-table")
@click.argument(
    "source",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.argument("label")
@click.option(
    "--table-offset",
    required=True,
    help="Verified file offset of the first pointer entry (e.g. $0F8000).",
)
@click.option(
    "--directive",
    type=click.Choice(["dl", "dw"], case_sensitive=False),
    default="dl",
    show_default=True,
    help="Asar pointer-table data directive; dw uses 2-byte entries, dl uses 3-byte entries.",
)
@click.option(
    "--entry-width",
    type=click.IntRange(min=1),
    default=None,
    show_default=False,
    help="Optional override for calculated entry locations.",
)
@click.option(
    "--source-revision",
    default=None,
    show_default=False,
    help="Revision to record; omitted values are marked unspecified.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write JSON to a new file instead of stdout; existing files are preserved.",
)
def inspect_pointer_table(
    source: Path,
    label: str,
    table_offset: str,
    directive: str,
    entry_width: int | None,
    source_revision: str | None,
    output: Path | None,
) -> None:
    """Parse a source-level Asar dl table to auditable JSON records.

    This command parses assembly text only. It does not read ROM bytes or
    resolve symbols to target offsets.
    """
    try:
        offset = _parse_offset_text(table_offset)
        source_text = source.read_text(encoding="utf-8")
        recorded_revision = source_revision or "unspecified"
        entries = parse_source_pointer_table(
            source_text,
            label,
            offset,
            directive=directive,
            entry_width=entry_width,
            source_revision=recorded_revision,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    payload = {
        "format": "zelda-suite-pointer-table",
        "format_version": 1,
        "source_file": source.name,
        "source_revision": recorded_revision,
        "table_label": label,
        "table_file_offset": offset,
        "entry_width": (
            entry_width
            if entry_width is not None
            else POINTER_DIRECTIVE_WIDTHS[directive.lower()]
        ),
        "entry_count": len(entries),
        "entries": [entry.to_dict() for entry in entries],
    }
    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    if output is None:
        click.echo(rendered, nl=False)
        return

    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc

    click.echo(f"Wrote {len(entries)} pointer-table entries to {output}")

@cli.command(name="inspect-data-table")
@click.argument(
    "source",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.argument("label")
@click.option(
    "--table-offset",
    required=True,
    help="Verified file offset of the first data-table entry (e.g. $048B90).",
)
@click.option(
    "--directive",
    type=click.Choice(["db", "dw", "dl"], case_sensitive=False),
    default="db",
    show_default=True,
    help="Asar data directive that defines the table element width.",
)
@click.option(
    "--entry-width",
    type=click.IntRange(min=1),
    default=None,
    show_default=False,
    help="Optional override for calculated entry locations.",
)
@click.option(
    "--parent-label",
    default=None,
    help="Global label for the containing brace-delimited block; scopes local labels.",
)
@click.option(
    "--end-label",
    default=None,
    help="Exclusive ending label when several tables share a block.",
)
@click.option(
    "--entry-count",
    type=click.IntRange(min=1),
    default=None,
    help="Optional exact number of entries expected in the bounded table.",
)
@click.option(
    "--source-revision",
    default=None,
    show_default=False,
    help="Revision to record; omitted values are marked unspecified.",
)
@click.option(
    "--include-comments",
    is_flag=True,
    help="Export source inline comments in version-2 JSON entries.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write JSON to a new file instead of stdout; existing files are preserved.",
)
def inspect_data_table(
    source: Path,
    label: str,
    table_offset: str,
    directive: str,
    entry_width: int | None,
    parent_label: str | None,
    end_label: str | None,
    entry_count: int | None,
    source_revision: str | None,
    include_comments: bool,
    output: Path | None,
) -> None:
    """Export raw Asar db/dw/dl values, optionally retaining inline comments."""
    try:
        offset = _parse_offset_text(table_offset)
        source_text = source.read_text(encoding="utf-8")
        recorded_revision = source_revision or "unspecified"
        normalized_directive = directive.lower()
        entries = parse_data_table(
            source_text,
            label,
            offset,
            directive=normalized_directive,
            entry_width=entry_width,
            parent_label=parent_label,
            end_label=end_label,
            source_revision=recorded_revision,
            expected_entry_count=entry_count,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    payload = {
        "format": "zelda-suite-data-table",
        "format_version": 2 if include_comments else 1,
        "source_file": source.name,
        "source_revision": recorded_revision,
        "parent_label": parent_label,
        "table_label": label,
        "end_label": end_label,
        "table_file_offset": offset,
        "directive": normalized_directive,
        "entry_width": (
            entry_width
            if entry_width is not None
            else DATA_DIRECTIVE_WIDTHS[normalized_directive]
        ),
        "entry_count": len(entries),
        "entries": [
            entry.to_dict(include_inline_comment=include_comments) for entry in entries
        ],
    }
    try:
        validate_source_export(payload)
    except AssetLoadError as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    if output is None:
        click.echo(rendered, nl=False)
        return

    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc

    click.echo(
        f"Wrote {len(entries)} data-table entries to {output} "
        f"(format v{payload['format_version']})"
    )


@cli.command(name="inspect-mixed-data-table")
@click.argument(
    "source",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.argument("label")
@click.option(
    "--table-offset",
    required=True,
    help="Source-commented file offset of the first byte (e.g. $0E80FC).",
)
@click.option(
    "--record-count",
    type=click.IntRange(min=1),
    default=None,
    help="Optional exact number of data-bearing source rows expected.",
)
@click.option(
    "--source-revision",
    default=None,
    show_default=False,
    help="Pinned source revision to record; omitted values are marked unspecified.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write JSON to a new file instead of stdout; existing files are preserved.",
)
def inspect_mixed_data_table(
    source: Path,
    label: str,
    table_offset: str,
    record_count: int | None,
    source_revision: str | None,
    output: Path | None,
) -> None:
    """Export raw mixed-width db/dw/dl rows with byte-accurate offsets."""
    try:
        offset = _parse_offset_text(table_offset)
        source_text = source.read_text(encoding="utf-8")
        revision = source_revision or "unspecified"
        table = parse_mixed_data_table(
            source_text,
            label,
            offset,
            expected_record_count=record_count,
        )
        payload = table.to_dict(source_file=source.name, source_revision=revision)
        validate_source_export(payload)
    except (OSError, UnicodeError, ValueError, AssetLoadError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
        return

    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc

    click.echo(
        f"Wrote {table.record_count} mixed-width records / {table.byte_count} bytes to {output}"
    )


@cli.command(name="audit-music-assets")
@click.option(
    "--registry",
    "registry_path",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
    default=None,
    help="Asset manifest (defaults to data/extracted/manifest.json).",
)
@click.option(
    "--index-asset",
    default="music-track-index",
    show_default=True,
    help="Registered music-track pointer index asset name.",
)
@click.option(
    "--payload-asset",
    default="music-payload-inventory",
    show_default=True,
    help="Registered music incbin inventory asset name.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write the JSON audit to a new file instead of stdout.",
)
@click.option(
    "--fail-on-findings",
    is_flag=True,
    help="Return exit status 1 when the report contains any error or warning.",
)
def audit_music_assets_command(
    registry_path: Path | None,
    index_asset: str,
    payload_asset: str,
    output: Path | None,
    fail_on_findings: bool,
) -> None:
    """Cross-check registered music pointers and payload declarations without a ROM."""
    try:
        report = audit_music_assets(
            registry_path or "data/extracted/manifest.json",
            index_asset_name=index_asset,
            payload_asset_name=payload_asset,
        )
    except (MusicAssetAuditError, AssetLoadError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        report,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
    else:
        try:
            with output.open("x", encoding="utf-8", newline="\n") as output_file:
                output_file.write(rendered)
        except FileExistsError as exc:
            raise click.ClickException(
                f"refusing to overwrite existing output: {output}"
            ) from exc
        except OSError as exc:
            raise click.ClickException(f"could not write {output}: {exc}") from exc
        summary = report["summary"]
        click.echo(
            f"Wrote music asset audit to {output}; "
            f"tracks={summary['track_entry_count']}, "
            f"missing_targets={summary['missing_payload_target_count']}, "
            f"payloads_missing_size={summary['payload_without_size_count']}, "
            f"errors={summary['error_count']}, warnings={summary['warning_count']}"
        )

    if fail_on_findings and report["summary"]["finding_count"]:
        raise click.exceptions.Exit(1)


@cli.command(name="inspect-music-track-index")
@click.argument(
    "source",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "--table-offset",
    required=True,
    help="Verified file offset of the first two-byte track pointer.",
)
@click.option(
    "--block-label",
    default="SongBank_Underworld_Main",
    show_default=True,
    help="Global source block containing the pointer table.",
)
@click.option(
    "--base-expression",
    default="SONG_POINTERS",
    show_default=True,
    help="Assembler base target that precedes the track pointer entries.",
)
@click.option(
    "--track-index-start",
    default="$01",
    show_default=True,
    help="Source track index annotated on the first pointer entry.",
)
@click.option(
    "--entry-count",
    type=click.IntRange(min=1),
    default=35,
    show_default=True,
    help="Expected count of two-byte pointer expressions.",
)
@click.option(
    "--source-revision",
    default=None,
    help="Pinned source revision to record in the export.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write JSON to a new file instead of stdout; existing files are preserved.",
)
def inspect_music_track_index(
    source: Path,
    table_offset: str,
    block_label: str,
    base_expression: str,
    track_index_start: str,
    entry_count: int,
    source_revision: str | None,
    output: Path | None,
) -> None:
    """Export source-indexed music pointer expressions without audio payloads."""
    try:
        table = parse_music_track_index(
            source.read_text(encoding="utf-8"),
            table_file_offset=_parse_offset_text(table_offset),
            source_revision=source_revision or "unspecified",
            source_file=source.name,
            block_label=block_label,
            base_expression=base_expression,
            track_index_start=_parse_offset_text(track_index_start),
            expected_entry_count=entry_count,
        )
        payload = table.to_dict()
        validate_source_export(payload)
    except (OSError, UnicodeError, ValueError, AssetLoadError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    if output is None:
        click.echo(rendered, nl=False)
        return

    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc

    empty_count = sum(entry.is_empty for entry in table.entries)
    alias_count = sum(entry.alias_of_track_index is not None for entry in table.entries)
    click.echo(
        f"Wrote {len(table.entries)} music track pointers to {output}; "
        f"{empty_count} empty and {alias_count} aliased entries"
    )



@cli.command(name="inspect-sprite-prep-dispatch")
@click.argument(
    "source",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "--source-revision",
    required=True,
    help="Pinned disassembly revision to record in the export.",
)
@click.option(
    "--entry-count",
    type=click.IntRange(min=1),
    default=243,
    show_default=True,
    help="Expected number of source-commented dispatch entries.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write JSON to a new file instead of stdout; existing files are preserved.",
)
def inspect_sprite_prep_dispatch(
    source: Path,
    source_revision: str,
    entry_count: int,
    output: Path | None,
) -> None:
    """Export source metadata for the inline SpritePrep_Main dispatch table."""
    try:
        source_text = source.read_text(encoding="utf-8")
        table = parse_sprite_prep_dispatch_table(
            source_text,
            source_revision=source_revision,
            source_file=source.name,
            expected_entry_count=entry_count,
        )
        payload = table.to_dict()
        validate_source_export(payload)
    except (OSError, UnicodeError, ValueError, AssetLoadError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
        return
    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc
    click.echo(
        f"Wrote {len(table.entries)} SpritePrep dispatch entries to {output}; "
        "inline table offset remains unestablished"
    )


@cli.command(name="audit-sprite-prep-dispatch")
@click.option(
    "--registry",
    "registry_path",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
    default=None,
    help="Asset manifest (defaults to data/extracted/manifest.json).",
)
@click.option(
    "--prep-asset",
    default="sprite-prep-dispatch",
    show_default=True,
    help="Registered source prep-dispatch asset.",
)
@click.option(
    "--active3-asset",
    default="sprite-active3-dispatch",
    show_default=True,
    help="Registered SpriteActive3-dispatch asset.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write the cross-reference report to a new file instead of stdout.",
)
def audit_sprite_prep_dispatch_command(
    registry_path: Path | None,
    prep_asset: str,
    active3_asset: str,
    output: Path | None,
) -> None:
    """Cross-reference the prep and active-loop sprite indexes by sprite ID."""
    try:
        report = audit_sprite_prep_dispatch(
            registry_path or "data/extracted/manifest.json",
            prep_asset_name=prep_asset,
            active3_asset_name=active3_asset,
        )
    except (SpritePrepDispatchAuditError, AssetLoadError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
        return
    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc
    summary = report["summary"]
    click.echo(
        f"Wrote sprite prep cross-reference to {output}; "
        f"prep={summary['prep_entry_count']}, "
        f"active3={summary['active3_entry_count']}, "
        f"shared_ids={summary['shared_sprite_id_count']}, "
        f"active3_only={summary['active3_only_sprite_id_count']}"
    )


@cli.command(name="inspect-sprite-dispatch")
@click.argument(
    "source",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "--table-offset",
    required=True,
    help="Verified file offset of the first dispatch entry, e.g. $0F0B33.",
)
@click.option(
    "--table-end-offset",
    required=True,
    help="Inclusive file offset of the final dispatch byte, e.g. $0F0BBA.",
)
@click.option(
    "--table-label",
    default="SpriteActive3_Table",
    show_default=True,
    help="Global assembly label for the dispatch table.",
)
@click.option(
    "--sprite-id-start",
    default="$79",
    show_default=True,
    help="Sprite type ID of the first table entry.",
)
@click.option(
    "--entry-count",
    type=click.IntRange(min=1),
    default=68,
    show_default=True,
    help="Expected number of two-byte handler entries.",
)
@click.option(
    "--source-revision",
    default=None,
    help="Pinned source revision to record in the export.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write JSON to a new file instead of stdout; existing files are preserved.",
)
def inspect_sprite_dispatch(
    source: Path,
    table_offset: str,
    table_end_offset: str,
    table_label: str,
    sprite_id_start: str,
    entry_count: int,
    source_revision: str | None,
    output: Path | None,
) -> None:
    """Export source metadata for the SpriteActive3 handler dispatch table."""
    try:
        source_text = source.read_text(encoding="utf-8")
        table = parse_sprite_dispatch_table(
            source_text,
            table_file_offset=_parse_offset_text(table_offset),
            table_end_offset=_parse_offset_text(table_end_offset),
            source_revision=source_revision or "unspecified",
            source_file=source.name,
            table_label=table_label,
            sprite_type_id_start=_parse_offset_text(sprite_id_start),
            expected_entry_count=entry_count,
        )
        payload = table.to_dict()
        validate_source_export(payload)
    except (OSError, UnicodeError, ValueError, AssetLoadError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    if output is None:
        click.echo(rendered, nl=False)
        return

    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc

    handler_counts: dict[str, int] = {}
    for entry in table.entries:
        handler_counts[entry.handler_label] = handler_counts.get(entry.handler_label, 0) + 1
    alias_id_count = sum(
        count for count in handler_counts.values() if count > 1
    )
    click.echo(
        f"Wrote {len(table.entries)} sprite dispatch records to {output}; "
        f"{alias_id_count} sprite IDs share aliased handlers"
    )


@cli.command(name="audit-text-message-index")
@click.option(
    "--registry",
    "registry_path",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
    default=None,
    help="Asset manifest (defaults to data/extracted/manifest.json).",
)
@click.option(
    "--asset",
    "asset_name",
    default="text-message-index",
    show_default=True,
    help="Registered text-message index asset name.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write the JSON audit to a new file instead of stdout.",
)
@click.option(
    "--fail-on-findings",
    is_flag=True,
    help="Return exit status 1 when source annotation or block-size findings exist.",
)
def audit_text_message_index_command(
    registry_path: Path | None,
    asset_name: str,
    output: Path | None,
    fail_on_findings: bool,
) -> None:
    """Summarize known source message-offset and declared block-size discrepancies."""
    try:
        report = audit_text_message_index(
            registry_path or "data/extracted/manifest.json",
            asset_name=asset_name,
        )
    except (TextMessageIndexAuditError, AssetLoadError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        report,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
    else:
        try:
            with output.open("x", encoding="utf-8", newline="\n") as output_file:
                output_file.write(rendered)
        except FileExistsError as exc:
            raise click.ClickException(
                f"refusing to overwrite existing output: {output}"
            ) from exc
        except OSError as exc:
            raise click.ClickException(f"could not write {output}: {exc}") from exc
        summary = report["summary"]
        click.echo(
            f"Wrote text message index audit to {output}; "
            f"messages={summary['message_count']}, "
            f"offset_mismatches={summary['offset_mismatch_count']}, "
            f"invalid_annotations={summary['invalid_offset_annotation_count']}, "
            f"missing_annotations={summary['missing_offset_annotation_count']}, "
            f"block_size_mismatches={summary['block_size_mismatch_count']}"
        )

    if fail_on_findings and report["summary"]["finding_count"]:
        raise click.exceptions.Exit(1)


@cli.command(name="inspect-text-messages")
@click.option(
    "--block",
    "blocks",
    type=click.Tuple(
        [
            click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
            str,
            str,
            str,
        ]
    ),
    multiple=True,
    required=True,
    help=(
        "Repeat for each source block: --block SOURCE BLOCK_LABEL START_OFFSET END_OFFSET. "
        "Offsets are the inclusive range annotated in the disassembly."
    ),
)
@click.option(
    "--source-revision",
    default=None,
    help="Pinned source revision to record in the export.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write JSON to a new file instead of stdout; existing files are preserved.",
)
def inspect_text_messages(
    blocks: tuple[tuple[Path, str, str, str], ...],
    source_revision: str | None,
    output: Path | None,
) -> None:
    """Index message IDs and source sizes without exporting encoded dialogue bytes."""
    try:
        recorded_revision = source_revision or "unspecified"
        source_specs = []
        for source_path, block_label, start_text, end_text in blocks:
            source_specs.append(
                MessageSourceBlock(
                    source_file=source_path.name,
                    block_label=block_label,
                    block_start_offset=_parse_offset_text(start_text),
                    block_end_offset=_parse_offset_text(end_text),
                    source_text=source_path.read_text(encoding="utf-8"),
                )
            )
        index = parse_text_message_index(
            source_specs,
            source_revision=recorded_revision,
        )
        payload = index.to_dict()
        validate_source_export(payload)
    except (OSError, UnicodeError, ValueError, AssetLoadError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    if output is None:
        click.echo(rendered, nl=False)
        return

    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc

    mismatch_count = sum(
        message.source_offset_matches_sequential is False
        for message in index.messages
    )
    block_mismatch_count = sum(
        not block.declared_bytes_match_block_size for block in index.source_blocks
    )
    click.echo(
        f"Wrote {len(index.messages)} source message records to {output}; "
        f"{mismatch_count} offset annotation mismatch(es), "
        f"{block_mismatch_count} block size mismatch(es) need review"
    )


@cli.command(name="audit-text-dictionary")
@click.option(
    "--registry",
    "registry_path",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
    default=None,
    help="Asset manifest (defaults to data/extracted/manifest.json).",
)
@click.option(
    "--pointer-asset",
    default="text-dictionary-pointers",
    show_default=True,
    help="Registered symbolic pointer-table asset name.",
)
@click.option(
    "--fragment-asset",
    default="text-dictionary-fragments",
    show_default=True,
    help="Registered fragment-inventory asset name.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write the JSON audit to a new file instead of stdout.",
)
@click.option(
    "--fail-on-findings",
    is_flag=True,
    help="Return exit status 1 when the report contains any error or warning.",
)
def audit_text_dictionary_command(
    registry_path: Path | None,
    pointer_asset: str,
    fragment_asset: str,
    output: Path | None,
    fail_on_findings: bool,
) -> None:
    """Cross-check registered dictionary pointers and fragments without a ROM."""
    try:
        report = audit_text_dictionary_assets(
            registry_path or "data/extracted/manifest.json",
            pointer_asset_name=pointer_asset,
            fragment_asset_name=fragment_asset,
        )
    except (TextDictionaryAuditError, AssetLoadError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        report,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
    else:
        try:
            with output.open("x", encoding="utf-8", newline="\n") as output_file:
                output_file.write(rendered)
        except FileExistsError as exc:
            raise click.ClickException(
                f"refusing to overwrite existing output: {output}"
            ) from exc
        except OSError as exc:
            raise click.ClickException(f"could not write {output}: {exc}") from exc
        summary = report["summary"]
        click.echo(
            f"Wrote text dictionary audit to {output}; "
            f"pointers={summary['pointer_entry_count']}, "
            f"fragments={summary['fragment_count']}, "
            f"cross_reference_mismatches={summary['cross_reference_mismatch_count']}, "
            f"source_extent_mismatches={summary['source_extent_mismatch_count']}, "
            f"errors={summary['error_count']}, warnings={summary['warning_count']}"
        )

    if fail_on_findings and report["summary"]["finding_count"]:
        raise click.exceptions.Exit(1)


@cli.command(name="inspect-text-dictionary")
@click.argument(
    "source",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "--pointer-table-offset",
    required=True,
    help="Verified file offset of DictionaryPointers (e.g. $074703).",
)
@click.option(
    "--data-offset",
    required=True,
    help="Verified file offset of DictionaryEntries (e.g. $0747C7).",
)
@click.option(
    "--pointer-table-label",
    default="DictionaryPointers",
    show_default=True,
    help="Global label for the dictionary pointer table.",
)
@click.option(
    "--data-label",
    default="DictionaryEntries",
    show_default=True,
    help="Global label for the dictionary fragment block.",
)
@click.option(
    "--source-revision",
    default=None,
    help="Pinned source revision to record in the export.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write JSON to a new file instead of stdout; existing files are preserved.",
)
def inspect_text_dictionary(
    source: Path,
    pointer_table_offset: str,
    data_offset: str,
    pointer_table_label: str,
    data_label: str,
    source_revision: str | None,
    output: Path | None,
) -> None:
    """Inventory dictionary pointer targets and source-declared fragment extents."""
    try:
        pointer_offset = _parse_offset_text(pointer_table_offset)
        fragment_offset = _parse_offset_text(data_offset)
        source_text = source.read_text(encoding="utf-8")
        recorded_revision = source_revision or "unspecified"
        fragments = parse_dictionary_fragment_inventory(
            source_text,
            pointer_table_file_offset=pointer_offset,
            data_file_offset=fragment_offset,
            source_revision=recorded_revision,
            pointer_table_label=pointer_table_label,
            data_label=data_label,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    payload = {
        "format": DICTIONARY_INVENTORY_FORMAT,
        "format_version": 1,
        "source_file": source.name,
        "source_revision": recorded_revision,
        "pointer_table_label": pointer_table_label,
        "pointer_table_file_offset": pointer_offset,
        "data_label": data_label,
        "data_file_offset": fragment_offset,
        "fragment_count": len(fragments),
        "fragments": [fragment.to_dict() for fragment in fragments],
    }
    try:
        validate_source_export(payload)
    except AssetLoadError as exc:
        raise click.ClickException(f"internal export validation failed: {exc}") from exc

    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    if output is None:
        click.echo(rendered, nl=False)
        return

    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc

    mismatch_count = sum(
        fragment.source_extent_matches_directive is False for fragment in fragments
    )
    click.echo(
        f"Wrote {len(fragments)} dictionary fragments to {output} "
        f"({mismatch_count} source extent mismatch(es) need review)"
    )


@cli.command(name="inspect-incbin")
@click.argument(
    "source",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "--source-revision",
    default=None,
    help="Revision to record; omitted values are marked unspecified.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write JSON to a new file instead of stdout; existing files are preserved.",
)
def inspect_incbin(
    source: Path, source_revision: str | None, output: Path | None
) -> None:
    """Inventory source-level incbin declarations without opening payloads."""
    recorded_revision = source_revision or "unspecified"
    try:
        source_text = source.read_text(encoding="utf-8")
        declarations = parse_incbin_inventory(
            source_text,
            source_file=source.name,
            source_revision=recorded_revision,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    payload = {
        "format": "zelda-suite-incbin-inventory",
        "format_version": 1,
        "source_file": source.name,
        "source_revision": recorded_revision,
        "declaration_count": len(declarations),
        "declarations": [item.to_dict() for item in declarations],
    }
    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    if output is None:
        click.echo(rendered, nl=False)
        return

    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc

    click.echo(f"Wrote {len(declarations)} incbin declarations to {output}")




@cli.command(name="audit-unresolved-table-expressions")
@click.option(
    "--registry",
    "registry_path",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
    default=None,
    help="Asset manifest (defaults to data/extracted/manifest.json).",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write the JSON audit to a new file instead of stdout.",
)
@click.option(
    "--fail-on-unresolved",
    is_flag=True,
    help="Return exit status 1 when unresolved expressions are present.",
)
def audit_unresolved_table_expressions_command(
    registry_path: Path | None,
    output: Path | None,
    fail_on_unresolved: bool,
) -> None:
    """Classify skipped data-table expressions without requiring a ROM."""
    try:
        report = audit_unresolved_table_expressions(
            registry_path or "data/extracted/manifest.json",
        )
    except (SourceExpressionAuditError, AssetLoadError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        report,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    if output is None:
        click.echo(rendered, nl=False)
    else:
        try:
            with output.open("x", encoding="utf-8", newline="\n") as output_file:
                output_file.write(rendered)
        except FileExistsError as exc:
            raise click.ClickException(
                f"refusing to overwrite existing output: {output}"
            ) from exc
        except OSError as exc:
            raise click.ClickException(f"could not write {output}: {exc}") from exc
        summary = report["summary"]
        click.echo(
            f"Wrote source-expression audit to {output}; "
            f"tables={summary['table_asset_count']}, "
            f"entries={summary['entry_count']}, "
            f"unresolved={summary['unresolved_expression_count']}"
        )

    if fail_on_unresolved and report["summary"]["unresolved_expression_count"]:
        raise click.exceptions.Exit(1)



@cli.command(name="audit-oam-allocation")
@click.option(
    "--registry",
    "registry_path",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
    default=None,
    help="Asset manifest (defaults to data/extracted/manifest.json).",
)
@click.option(
    "--table-asset",
    default="oam-buffer-position-table",
    show_default=True,
    help="Registered OAM allocator table asset name.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write the JSON audit to a new file instead of stdout.",
)
def audit_oam_allocation_command(
    registry_path: Path | None,
    table_asset: str,
    output: Path | None,
) -> None:
    """Structure the six OAM region limits and 48 overflow fallback words."""
    try:
        report = audit_oam_allocation(
            registry_path or "data/extracted/manifest.json",
            table_asset_name=table_asset,
        )
    except (OAMAllocationAuditError, AssetLoadError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        report,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
    else:
        try:
            with output.open("x", encoding="utf-8", newline="\n") as output_file:
                output_file.write(rendered)
        except FileExistsError as exc:
            raise click.ClickException(
                f"refusing to overwrite existing output: {output}"
            ) from exc
        except OSError as exc:
            raise click.ClickException(f"could not write {output}: {exc}") from exc
        summary = report["summary"]
        click.echo(
            f"Wrote OAM allocation audit to {output}; "
            f"regions={summary['region_count']}, "
            f"limits={summary['limit_entry_count']}, "
            f"fallback_points={summary['fallback_point_count']}"
        )


@cli.command(name="audit-incbin-inventory")
@click.option(
    "--registry",
    "registry_path",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
    default=None,
    help="Asset manifest (defaults to data/extracted/manifest.json).",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write the JSON audit to a new file instead of stdout.",
)
@click.option(
    "--fail-on-findings",
    is_flag=True,
    help="Return exit status 1 when metadata gaps, range mismatches, or candidate overlaps exist.",
)
def audit_incbin_inventory_command(
    registry_path: Path | None,
    output: Path | None,
    fail_on_findings: bool,
) -> None:
    """Audit registered incbin source annotations without opening payloads or ROMs."""
    try:
        report = audit_incbin_inventories(
            registry_path or "data/extracted/manifest.json",
        )
    except (IncbinInventoryAuditError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        report,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    if output is None:
        click.echo(rendered, nl=False)
    else:
        try:
            with output.open("x", encoding="utf-8", newline="\n") as output_file:
                output_file.write(rendered)
        except FileExistsError as exc:
            raise click.ClickException(
                f"refusing to overwrite existing output: {output}"
            ) from exc
        except OSError as exc:
            raise click.ClickException(f"could not write {output}: {exc}") from exc
        summary = report["summary"]
        click.echo(
            f"Wrote incbin inventory audit to {output}; "
            f"inventories={summary['inventory_count']}, "
            f"declarations={summary['declaration_count']}, "
            f"metadata_gaps={summary['metadata_gap_count']}, "
            f"range_mismatches={summary['range_mismatch_count']}, "
            f"candidate_overlaps={summary['candidate_overlap_count']}"
        )

    if fail_on_findings and report["summary"]["finding_count"]:
        raise click.exceptions.Exit(1)


@cli.command(name="diff-rom")
@click.argument(
    "base_rom",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.argument(
    "modified_rom",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write diff JSON to a new file instead of stdout.",
)
def diff_rom_files(base_rom: Path, modified_rom: Path, output: Path | None) -> None:
    """Create a deterministic, read-only diff between a base ROM and candidate ROM."""
    try:
        base_bytes = read_rom_bytes(base_rom)
        modified_bytes = read_rom_bytes(modified_rom)
    except ROMImageInspectionError as exc:
        raise click.ClickException(str(exc)) from exc

    if len(base_bytes) != EXPECTED_US_ROM_SIZE:
        raise click.ClickException(
            f"base ROM must be the expected headerless 1 MiB image "
            f"({EXPECTED_US_ROM_SIZE:,} bytes); got {len(base_bytes):,}. "
            "Use inspect-rom to diagnose the file."
        )
    if not modified_bytes:
        raise click.ClickException("modified ROM image is empty")
    if (
        len(modified_bytes) == EXPECTED_US_ROM_SIZE + COPIER_HEADER_SIZE
        or (
            len(modified_bytes) > SNES_ROM_BANK_SIZE
            and len(modified_bytes) % SNES_ROM_BANK_SIZE == COPIER_HEADER_SIZE
        )
    ):
        raise click.ClickException(
            "modified ROM size suggests a 512-byte copier header; "
            "remove/resolve the header locally before diffing"
        )

    byte_diff = compare_bytes(base_bytes, modified_bytes)
    payload = {
        "format": "zelda-suite-rom-file-diff",
        "format_version": 1,
        "base_rom": {
            "filename": base_rom.name,
            "size_bytes": len(base_bytes),
            "sha256": sha256_rom_bytes(base_bytes),
        },
        "modified_rom": {
            "filename": modified_rom.name,
            "size_bytes": len(modified_bytes),
            "sha256": sha256_rom_bytes(modified_bytes),
        },
        "diff": byte_diff.to_dict(),
    }
    rendered = json.dumps(
        payload,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    if output is None:
        click.echo(rendered, nl=False)
        return

    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc

    click.echo(f"Wrote ROM file diff to {output}")


@cli.command(name="inspect-rom")
@click.argument(
    "rom_path",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write metadata JSON to a new file instead of stdout.",
)
def inspect_rom(rom_path: Path, output: Path | None) -> None:
    """Inspect a local ROM's size, SHA-256, header assessment, and LoROM mapping."""
    try:
        inspection = inspect_rom_image(rom_path)
    except ROMImageInspectionError as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        inspection.to_dict(),
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    if output is None:
        click.echo(rendered, nl=False)
        return

    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc

    click.echo(f"Wrote ROM inspection metadata to {output}")



@cli.command(name="verify-rom-tables")
@click.argument(
    "rom_path",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "--registry",
    "registry_path",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
    default=None,
    help="Asset manifest (defaults to data/extracted/manifest.json).",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write the JSON report to a new file instead of stdout.",
)
@click.option(
    "--include-skipped-expressions",
    is_flag=True,
    default=False,
    help=(
        "Emit report format v2 with non-evaluating classifications for unresolved "
        "expressions."
    ),
)
def verify_rom_tables_command(
    rom_path: Path,
    registry_path: Path | None,
    output: Path | None,
    include_skipped_expressions: bool,
) -> None:
    """Compare numeric registered source-table literals with local ROM bytes."""
    try:
        report = verify_registered_scalar_tables(
            rom_path,
            registry_path or "data/extracted/manifest.json",
            include_skipped_expressions=include_skipped_expressions,
        )
    except (AssetLoadError, ROMTableVerificationError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        report,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    if output is None:
        click.echo(rendered, nl=False)
    else:
        try:
            with output.open("x", encoding="utf-8", newline="\n") as output_file:
                output_file.write(rendered)
        except FileExistsError as exc:
            raise click.ClickException(
                f"refusing to overwrite existing output: {output}"
            ) from exc
        except OSError as exc:
            raise click.ClickException(f"could not write {output}: {exc}") from exc
        summary = report["summary"]
        summary_text = (
            f"Wrote ROM table verification report to {output}; "
            f"checked={summary['checked_entries']}, "
            f"skipped={summary['skipped_entries']}, "
            f"mismatches={summary['mismatches']}"
        )
        if include_skipped_expressions:
            summary_text += f", unresolved={summary['unresolved_expression_count']}"
        click.echo(summary_text)

    if report["summary"]["mismatches"]:
        raise click.exceptions.Exit(1)



@cli.command(name="inspect-dungeon-chest-data")
@click.argument(
    "source",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "--source-revision",
    required=True,
    help="Pinned disassembly revision to record in the export.",
)
@click.option(
    "--entry-count",
    type=click.IntRange(min=1),
    default=168,
    show_default=True,
    help="Expected number of packed three-byte chest entries.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write the JSON export to a new file instead of stdout.",
)
def inspect_dungeon_chest_data(
    source: Path,
    source_revision: str,
    entry_count: int,
    output: Path | None,
) -> None:
    """Export raw room/item fields from Dungeon_ChestData without ROM reads."""
    try:
        source_text = source.read_text(encoding="utf-8")
        table = parse_dungeon_chest_data(
            source_text,
            source_revision=source_revision,
            source_file=source.name,
            expected_entry_count=entry_count,
        )
        payload = table.to_dict()
        validate_source_export(payload)
    except (OSError, UnicodeError, ValueError, AssetLoadError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        payload,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
        return
    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc
    click.echo(
        f"Wrote {len(table.entries)} chest entries to {output}; "
        "source-range offsets remain unverified"
    )


@cli.command(name="audit-dungeon-chest-data")
@click.option(
    "--registry",
    "registry_path",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
    default=None,
    help="Asset manifest (defaults to data/extracted/manifest.json).",
)
@click.option(
    "--asset",
    "asset_name",
    default="dungeon-chest-data",
    show_default=True,
    help="Registered packed dungeon chest data asset name.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write the JSON audit to a new file instead of stdout.",
)
def audit_dungeon_chest_data_command(
    registry_path: Path | None,
    asset_name: str,
    output: Path | None,
) -> None:
    """Summarize raw chest-room values, big-chest flags, and repeated rooms."""
    try:
        report = audit_dungeon_chest_data(
            registry_path or "data/extracted/manifest.json",
            asset_name=asset_name,
        )
    except (DungeonChestDataAuditError, AssetLoadError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        report,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
        return
    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc
    summary = report["summary"]
    click.echo(
        f"Wrote dungeon chest data audit to {output}; "
        f"entries={summary['entry_count']}, "
        f"unique_rooms={summary['unique_room_value_count']}, "
        f"repeated_rooms={summary['room_values_with_multiple_entries']}, "
        f"big_chests={summary['big_chest_count']}"
    )



@cli.command(name="inspect-shop-item-handlers")
@click.argument(
    "source",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "--source-revision",
    required=True,
    help="Pinned disassembly revision to record in the export.",
)
@click.option(
    "--entry-count",
    type=click.IntRange(min=1),
    default=7,
    show_default=True,
    help="Expected number of standard shopkeeper purchase handlers.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write JSON to a new file instead of stdout; existing files are preserved.",
)
def inspect_shop_item_handlers(
    source: Path,
    source_revision: str,
    entry_count: int,
    output: Path | None,
) -> None:
    """Export source-coded prices and receipt selectors for standard shop handlers."""
    try:
        table = parse_shop_item_handlers(
            source.read_text(encoding="utf-8"),
            source_revision=source_revision,
            source_file=source.name,
            expected_entry_count=entry_count,
        )
        payload = table.to_dict()
        validate_source_export(payload)
    except (OSError, UnicodeError, ValueError, AssetLoadError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        payload,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
        return
    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc
    click.echo(
        f"Wrote {len(table.entries)} shop purchase handlers to {output}; "
        "room-specific shop stock and receipt item names remain unresolved"
    )



@cli.command(name="audit-item-receipt-annotations")
@click.option(
    "--registry",
    "registry_path",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
    default=None,
    help="Asset manifest (defaults to data/extracted/manifest.json).",
)
@click.option(
    "--asset",
    "asset_name",
    default="item-receipt-graphics-indices",
    show_default=True,
    help="Registered dense receive-item graphics-index table.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write the JSON audit to a new file instead of stdout.",
)
def audit_item_receipt_annotations_command(
    registry_path: Path | None,
    asset_name: str,
    output: Path | None,
) -> None:
    """Compare source-comment item IDs to dense table indexes without normalizing them."""
    try:
        report = audit_item_receipt_annotations(
            registry_path or "data/extracted/manifest.json",
            asset_name=asset_name,
        )
    except (ItemReceiptAnnotationAuditError, AssetLoadError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        report,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
        return
    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc
    summary = report["summary"]
    click.echo(
        f"Wrote item-receipt annotation audit to {output}; "
        f"entries={summary['table_entry_count']}, "
        f"comment_id_mismatches={summary['source_comment_ids_mismatched_count']}, "
        f"missing_comment_ids={report['missing_source_comment_ids']}"
    )



@cli.command(name="inspect-potion-shop-transactions")
@click.argument(
    "source",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "--source-revision",
    required=True,
    help="Pinned disassembly revision to record in the export.",
)
@click.option(
    "--entry-count",
    type=click.IntRange(min=1),
    default=3,
    show_default=True,
    help="Expected number of priced potion-shop transactions.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write JSON to a new file instead of stdout; existing files are preserved.",
)
def inspect_potion_shop_transactions(
    source: Path,
    source_revision: str,
    entry_count: int,
    output: Path | None,
) -> None:
    """Export source-coded rupee prices and receipt selectors for the potion shop."""
    try:
        table = parse_potion_shop_transactions(
            source.read_text(encoding="utf-8"),
            source_revision=source_revision,
            source_file=source.name,
            expected_entry_count=entry_count,
        )
        payload = table.to_dict()
        validate_source_export(payload)
    except (OSError, UnicodeError, ValueError, AssetLoadError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        payload,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
        return
    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc
    click.echo(
        f"Wrote {len(table.entries)} potion-shop transactions to {output}; "
        "price behavior and receipt item names remain unverified"
    )


@cli.command(name="audit-potion-shop-transactions")
@click.option(
    "--registry",
    "registry_path",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
    default=None,
    help="Asset manifest (defaults to data/extracted/manifest.json).",
)
@click.option(
    "--asset",
    "asset_name",
    default="potion-shop-transactions",
    show_default=True,
    help="Registered potion-shop transaction asset.",
)
@click.option(
    "--receipt-asset",
    "receipt_asset_name",
    default="item-receipt-layout",
    show_default=True,
    help="Registered positional receive-item layout used by receipt selectors.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write the JSON audit to a new file instead of stdout.",
)
def audit_potion_shop_transactions_command(
    registry_path: Path | None,
    asset_name: str,
    receipt_asset_name: str,
    output: Path | None,
) -> None:
    """Join potion-shop transactions to raw receive-item slots by position."""
    try:
        report = audit_potion_shop_transactions(
            registry_path or "data/extracted/manifest.json",
            asset_name=asset_name,
            receipt_asset_name=receipt_asset_name,
        )
    except (PotionShopTransactionsAuditError, AssetLoadError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        report,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
        return
    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc
    summary = report["summary"]
    click.echo(
        f"Wrote potion-shop transaction audit to {output}; "
        f"transactions={summary['transaction_count']}, "
        f"receipt_slots={summary['distinct_receipt_item_index_count']}, "
        f"price_range={summary['minimum_price_value']}-{summary['maximum_price_value']}, "
        f"comment_id_mismatches={summary['receipt_indexes_with_comment_id_mismatch']}"
    )


@cli.command(name="audit-shop-item-handlers")
@click.option(
    "--registry",
    "registry_path",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
    default=None,
    help="Asset manifest (defaults to data/extracted/manifest.json).",
)
@click.option(
    "--asset",
    "asset_name",
    default="shop-item-handlers",
    show_default=True,
    help="Registered standard shopkeeper purchase-handler asset.",
)
@click.option(
    "--receipt-asset",
    "receipt_asset_name",
    default="item-receipt-layout",
    show_default=True,
    help="Registered positional receive-item layout used by receipt selectors.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write the JSON audit to a new file instead of stdout.",
)
def audit_shop_item_handlers_command(
    registry_path: Path | None,
    asset_name: str,
    receipt_asset_name: str,
    output: Path | None,
) -> None:
    """Join standard shop purchase handlers to raw receive-item slots by index."""
    try:
        report = audit_shop_item_handlers(
            registry_path or "data/extracted/manifest.json",
            asset_name=asset_name,
            receipt_asset_name=receipt_asset_name,
        )
    except (ShopItemHandlersAuditError, AssetLoadError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        report,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
        return
    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc
    summary = report["summary"]
    click.echo(
        f"Wrote shop-item handler audit to {output}; "
        f"handlers={summary['handler_count']}, "
        f"receipt_slots={summary['distinct_receipt_item_index_count']}, "
        f"price_range={summary['minimum_price_value']}-{summary['maximum_price_value']}"
    )



@cli.command(name="inspect-special-shop-transactions")
@click.argument(
    "bomb_shop_source",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.argument(
    "bottle_vendor_source",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "--source-revision",
    required=True,
    help="Pinned disassembly revision to record in the export.",
)
@click.option(
    "--entry-count",
    type=click.IntRange(min=1),
    default=3,
    show_default=True,
    help="Expected number of Bomb Shop and Bottle Vendor purchase records.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write JSON to a new file instead of stdout; existing files are preserved.",
)
def inspect_special_shop_transactions(
    bomb_shop_source: Path,
    bottle_vendor_source: Path,
    source_revision: str,
    entry_count: int,
    output: Path | None,
) -> None:
    """Export Bomb Shop and Bottle Vendor purchases without resolving item identities."""
    try:
        table = parse_special_shop_transactions(
            bomb_shop_source.read_text(encoding="utf-8"),
            bottle_vendor_source.read_text(encoding="utf-8"),
            source_revision=source_revision,
            bomb_shop_source_file=bomb_shop_source.name,
            bottle_vendor_source_file=bottle_vendor_source.name,
            expected_entry_count=entry_count,
        )
        payload = table.to_dict()
        validate_source_export(payload)
    except (OSError, UnicodeError, ValueError, AssetLoadError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        payload,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
        return
    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc
    non_receipt = sum(entry.receipt_item_index is None for entry in table.entries)
    click.echo(
        f"Wrote {len(table.entries)} special-shop transactions to {output}; "
        f"receipt_selectors={len(table.entries) - non_receipt}, "
        f"non_receipt_rewards={non_receipt}; prices and reward behavior remain source-only"
    )


@cli.command(name="audit-special-shop-transactions")
@click.option(
    "--registry",
    "registry_path",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
    default=None,
    help="Asset manifest (defaults to data/extracted/manifest.json).",
)
@click.option(
    "--asset",
    "asset_name",
    default="special-shop-transactions",
    show_default=True,
    help="Registered Bomb Shop and Bottle Vendor transaction asset.",
)
@click.option(
    "--receipt-asset",
    "receipt_asset_name",
    default="item-receipt-layout",
    show_default=True,
    help="Registered raw receive-item layout used by receipt selectors.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write the JSON audit to a new file instead of stdout.",
)
def audit_special_shop_transactions_command(
    registry_path: Path | None,
    asset_name: str,
    receipt_asset_name: str,
    output: Path | None,
) -> None:
    """Cross-reference special-shop receipt selectors to raw receive-item slots."""
    try:
        report = audit_special_shop_transactions(
            registry_path or "data/extracted/manifest.json",
            asset_name=asset_name,
            receipt_asset_name=receipt_asset_name,
        )
    except (SpecialShopTransactionsAuditError, AssetLoadError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        report,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
        return
    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc
    summary = report["summary"]
    click.echo(
        f"Wrote special-shop transaction audit to {output}; "
        f"transactions={summary['transaction_count']}, "
        f"receipt_slots={summary['distinct_receipt_item_index_count']}, "
        f"non_receipt_rewards={summary['non_receipt_reward_count']}"
    )



@cli.command(name="inspect-paid-overworld-interactions")
@click.argument(
    "archery_source",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.argument(
    "digging_source",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.argument(
    "fortune_source",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.argument(
    "kiki_source",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.argument(
    "ponds_source",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.argument(
    "zora_source",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "--source-revision",
    required=True,
    help="Pinned disassembly revision to record in the export.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write JSON to a new file instead of stdout; existing files are preserved.",
)
def inspect_paid_overworld_interactions(
    archery_source: Path,
    digging_source: Path,
    fortune_source: Path,
    kiki_source: Path,
    ponds_source: Path,
    zora_source: Path,
    source_revision: str,
    output: Path | None,
) -> None:
    """Export source-coded rupee fees and Digging Game reward paths."""
    source_paths = {
        "sprite_archery_game_guy.asm": archery_source,
        "sprite_digging_game_guy.asm": digging_source,
        "sprite_fortune_teller.asm": fortune_source,
        "sprite_kiki.asm": kiki_source,
        "sprite_ponds.asm": ponds_source,
        "sprite_zora_king.asm": zora_source,
    }
    try:
        sources = {
            name: path.read_text(encoding="utf-8")
            for name, path in source_paths.items()
        }
        payload = parse_paid_overworld_interactions(
            sources,
            source_revision=source_revision,
        )
        validate_source_export(payload)
    except (OSError, UnicodeError, ValueError, AssetLoadError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        payload,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
        return
    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc
    click.echo(
        f"Wrote {payload['interaction_count']} paid overworld interactions to {output}; "
        "fees and source reward paths remain unverified against ROM execution"
    )


@cli.command(name="audit-paid-overworld-interactions")
@click.option(
    "--registry",
    "registry_path",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
    default=None,
    help="Asset manifest (defaults to data/extracted/manifest.json).",
)
@click.option(
    "--asset",
    "asset_name",
    default="paid-overworld-interactions",
    show_default=True,
    help="Registered paid-overworld interaction asset.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write the audit JSON to a new file instead of stdout.",
)
def audit_paid_overworld_interactions_command(
    registry_path: Path | None,
    asset_name: str,
    output: Path | None,
) -> None:
    """Summarize source-coded paid interactions and the Digging Game reward table."""
    try:
        report = audit_paid_overworld_interactions(
            registry_path or "data/extracted/manifest.json",
            asset_name=asset_name,
        )
    except (PaidOverworldInteractionsAuditError, AssetLoadError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        report,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
        return
    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc
    summary = report["summary"]
    click.echo(
        f"Wrote paid-overworld audit to {output}; "
        f"interactions={summary['interaction_count']}, "
        f"fee_range={summary['minimum_fee_value']}-{summary['maximum_fee_value']}, "
        f"digging_reward_slots={summary['digging_game_dispatch_entry_count']}"
    )


@cli.command(name="audit-dungeon-room-assets")
@click.option(
    "--registry",
    "registry_path",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
    default=None,
    help="Asset manifest (defaults to data/extracted/manifest.json).",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write the JSON audit to a new file instead of stdout.",
)
@click.option(
    "--fail-on-findings",
    is_flag=True,
    help="Return exit status 1 when an error or warning is present.",
)
def audit_dungeon_room_assets_command(
    registry_path: Path | None,
    output: Path | None,
    fail_on_findings: bool,
) -> None:
    """Cross-reference the registered dungeon pointer and room payload assets."""
    try:
        report = audit_dungeon_room_assets(
            registry_path or "data/extracted/manifest.json"
        )
    except (DungeonRoomAssetAuditError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        report,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
    else:
        try:
            with output.open("x", encoding="utf-8", newline="\n") as output_file:
                output_file.write(rendered)
        except FileExistsError as exc:
            raise click.ClickException(
                f"refusing to overwrite existing output: {output}"
            ) from exc
        except OSError as exc:
            raise click.ClickException(f"could not write {output}: {exc}") from exc
        summary = report["summary"]
        click.echo(
            f"Wrote dungeon-room asset audit to {output}; "
            f"pointers={summary['pointer_entry_count']}, "
            f"targets={summary['unique_pointer_target_label_count']}, "
            f"payloads={summary['payload_declaration_count']}, "
            f"missing_targets={summary['missing_payload_target_count']}, "
            f"unreferenced_payloads={summary['unreferenced_payload_count']}, "
            f"errors={summary['error_count']}, warnings={summary['warning_count']}"
        )

    if fail_on_findings and report["summary"]["finding_count"]:
        raise click.exceptions.Exit(1)



@cli.command(name="audit-dungeon-room-door-pointers")
@click.option(
    "--registry",
    "registry_path",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
    default=None,
    help="Asset manifest (defaults to data/extracted/manifest.json).",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write the JSON audit to a new file instead of stdout.",
)
@click.option(
    "--fail-on-findings",
    is_flag=True,
    help="Return exit status 1 when an error or warning is present.",
)
def audit_dungeon_room_door_pointers_command(
    registry_path: Path | None,
    output: Path | None,
    fail_on_findings: bool,
) -> None:
    """Audit door-pointer addends against source-declared room payload sizes."""
    try:
        report = audit_dungeon_room_door_pointer_bounds(
            registry_path or "data/extracted/manifest.json"
        )
    except (DungeonRoomDoorPointerAuditError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        report,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
    else:
        try:
            with output.open("x", encoding="utf-8", newline="\n") as output_file:
                output_file.write(rendered)
        except FileExistsError as exc:
            raise click.ClickException(
                f"refusing to overwrite existing output: {output}"
            ) from exc
        except OSError as exc:
            raise click.ClickException(f"could not write {output}: {exc}") from exc
        summary = report["summary"]
        click.echo(
            f"Wrote dungeon door-pointer audit to {output}; "
            f"pointers={summary['pointer_entry_count']}, "
            f"in_bounds={summary['addend_in_bounds_count']}, "
            f"out_of_bounds={summary['addend_out_of_bounds_count']}, "
            f"unknown_bounds={summary['addend_bounds_unknown_count']}, "
            f"errors={summary['error_count']}, warnings={summary['warning_count']}"
        )

    if fail_on_findings and report["summary"]["finding_count"]:
        raise click.exceptions.Exit(1)


@cli.command(name="verify-dungeon-room-pointers")
@click.argument(
    "rom_path",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "--registry",
    "registry_path",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
    default=None,
    help="Asset manifest (defaults to data/extracted/manifest.json).",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write the JSON report to a new file instead of stdout.",
)
def verify_dungeon_room_pointers_command(
    rom_path: Path,
    registry_path: Path | None,
    output: Path | None,
) -> None:
    """Compare room-table long pointers with source-commented payload offsets."""
    try:
        report = verify_dungeon_room_pointers(
            rom_path,
            registry_path or "data/extracted/manifest.json",
        )
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        report,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    if output is None:
        click.echo(rendered, nl=False)
    else:
        try:
            with output.open("x", encoding="utf-8", newline="\n") as output_file:
                output_file.write(rendered)
        except FileExistsError as exc:
            raise click.ClickException(
                f"refusing to overwrite existing output: {output}"
            ) from exc
        except OSError as exc:
            raise click.ClickException(f"could not write {output}: {exc}") from exc
        click.echo(
            f"Wrote dungeon-room pointer verification report to {output}; "
            f"checked={report['pointer_table']['checked_comparisons']}, "
            f"mismatches={report['pointer_table']['mismatch_count']}"
        )

    if report["pointer_table"]["mismatch_count"]:
        raise click.exceptions.Exit(1)


@cli.command(name="verify-text-dictionary-pointers")
@click.argument(
    "rom_path",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "--registry",
    "registry_path",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
    default=None,
    help="Asset manifest (defaults to data/extracted/manifest.json).",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write the JSON report to a new file instead of stdout.",
)
def verify_text_dictionary_pointers_command(
    rom_path: Path,
    registry_path: Path | None,
    output: Path | None,
) -> None:
    """Compare the 98 dictionary pointer words to source-offset candidates."""
    try:
        report = verify_text_dictionary_pointers(
            rom_path,
            registry_path or "data/extracted/manifest.json",
        )
    except (TextDictionaryPointerVerificationError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        report,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
    else:
        try:
            with output.open("x", encoding="utf-8", newline="\n") as output_file:
                output_file.write(rendered)
        except FileExistsError as exc:
            raise click.ClickException(
                f"refusing to overwrite existing output: {output}"
            ) from exc
        except OSError as exc:
            raise click.ClickException(f"could not write {output}: {exc}") from exc
        summary = report["pointer_table"]
        click.echo(
            f"Wrote text dictionary pointer verification report to {output}; "
            f"checked={summary['checked_comparisons']}, "
            f"mismatches={summary['mismatch_count']}, "
            f"source_extent_warnings={summary['source_extent_mismatch_count']}"
        )

    if report["pointer_table"]["mismatch_count"]:
        raise click.exceptions.Exit(1)


@cli.command(name="verify-text-message-bytes")
@click.argument(
    "rom_path",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "--block",
    "blocks",
    type=click.Tuple([
        click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
        str,
        str,
        str,
    ]),
    multiple=True,
    required=True,
    help=(
        "Repeat for each source block: --block SOURCE BLOCK_LABEL START_OFFSET END_OFFSET. "
        "Offsets are inclusive source-declared file offsets."
    ),
)
@click.option(
    "--source-revision",
    default=PINNED_TEXT_SOURCE_REVISION,
    show_default=True,
    help="Source revision to record in the report; use a distinct label for synthetic fixtures.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write the JSON report to a new file instead of stdout.",
)
def verify_text_message_bytes_command(
    rom_path: Path,
    blocks: tuple[tuple[Path, str, str, str], ...],
    source_revision: str,
    output: Path | None,
) -> None:
    """Compare literal encoded message bytes with source declarations without decoding text."""
    try:
        source_blocks = [
            MessageSourceBlock(
                source_file=source_path.name,
                block_label=block_label,
                block_start_offset=_parse_offset_text(start_text),
                block_end_offset=_parse_offset_text(end_text),
                source_text=source_path.read_text(encoding="utf-8"),
            )
            for source_path, block_label, start_text, end_text in blocks
        ]
        report = verify_text_message_bytes(
            rom_path,
            source_blocks,
            source_revision=source_revision,
        )
    except (OSError, UnicodeError, TextMessageByteVerificationError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        report,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
    else:
        try:
            with output.open("x", encoding="utf-8", newline="\n") as output_file:
                output_file.write(rendered)
        except FileExistsError as exc:
            raise click.ClickException(
                f"refusing to overwrite existing output: {output}"
            ) from exc
        except OSError as exc:
            raise click.ClickException(f"could not write {output}: {exc}") from exc
        summary = report["summary"]
        click.echo(
            f"Wrote text message byte verification report to {output}; "
            f"messages={summary['message_count']}, "
            f"checked={summary['checked_byte_count']}, "
            f"mismatches={summary['mismatch_byte_count']}, "
            f"source_warnings={summary['source_finding_count']}"
        )

    if report["summary"]["mismatch_byte_count"]:
        raise click.exceptions.Exit(1)


@cli.command(name="verify-overworld-hidden-items")
@click.argument(
    "rom_path",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "--source",
    "source_path",
    type=click.Path(
        path_type=Path,
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
    default="reference/AsarUSALTTPDisassembly/Bank1B.asm",
    show_default=True,
    help="Pinned Bank1B.asm source used to derive pointer targets and record offsets.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write the JSON report to a new file instead of stdout.",
)
def verify_overworld_hidden_items_command(
    rom_path: Path,
    source_path: Path,
    output: Path | None,
) -> None:
    """Verify source-derived overworld hidden-item pointers, records, sentinels and Map16 words."""
    try:
        source = source_path.read_text(encoding="utf-8")
        report = verify_overworld_hidden_items(
            rom_path,
            source,
        )
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        report,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    if output is None:
        click.echo(rendered, nl=False)
    else:
        try:
            with output.open("x", encoding="utf-8", newline="\n") as output_file:
                output_file.write(rendered)
        except FileExistsError as exc:
            raise click.ClickException(
                f"refusing to overwrite existing output: {output}"
            ) from exc
        except OSError as exc:
            raise click.ClickException(f"could not write {output}: {exc}") from exc
        click.echo(
            f"Wrote hidden-item verification report to {output}; "
            f"checked={report['checked_comparisons']}, "
            f"mismatches={report['mismatch_count']}"
        )

    if report["mismatch_count"]:
        raise click.exceptions.Exit(1)


@cli.command(name="inspect-overworld-hidden-items")
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write the JSON report to a new file instead of stdout.",
)
def inspect_overworld_hidden_items_command(output: Path | None) -> None:
    """Emit the pinned overworld hidden-item source layout without reading a ROM."""
    source_path = Path("reference/AsarUSALTTPDisassembly/Bank1B.asm")
    try:
        source = source_path.read_text(encoding="utf-8")
        layout = parse_overworld_hidden_item_source(source)
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    payload = {
        "format": "zelda-suite-overworld-hidden-item-source-layout",
        "format_version": 1,
        "source_file": source_path.as_posix(),
        "source_revision": layout["source_revision"],
        "pointer_table_offset": layout["pointer_table_offset"],
        "pointer_count": len(layout["pointer_entries"]),
        "pointer_entries": layout["pointer_entries"],
        "data_start_offset": layout["data_start_offset"],
        "data_end_exclusive": layout["data_end_exclusive"],
        "data_region_size_bytes": (
            layout["data_end_exclusive"] - layout["data_start_offset"]
        ),
        "distinct_target_label_count": len(layout["label_offsets"]),
        "label_offsets": layout["label_offsets"],
        "record_count": len(layout["records"]),
        "records": layout["records"],
        "sentinel_count": len(layout["sentinels"]),
        "sentinels": layout["sentinels"],
        "area_count": len(layout["area_lists"]),
        "area_lists": layout["area_lists"],
        "replacement_word_count": len(layout["replacement_words"]),
        "replacement_words": layout["replacement_words"],
        "rom_verified": False,
        "semantic_values_decoded": False,
    }
    rendered = json.dumps(
        payload,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    if output is None:
        click.echo(rendered, nl=False)
        return

    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc

    click.echo(
        f"Wrote hidden-item source-layout report to {output}; "
        f"pointers={payload['pointer_count']}, records={payload['record_count']}, "
        f"sentinels={payload['sentinel_count']}, areas={payload['area_count']}"
    )


@cli.command(name="join-item-receipt-tables")
@click.option(
    "--registry",
    "registry_path",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
    default=None,
    help="Asset manifest (defaults to data/extracted/manifest.json).",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write the joined JSON view to a new file instead of stdout.",
)
def join_item_receipt_tables_command(
    registry_path: Path | None,
    output: Path | None,
) -> None:
    """Join the receive-item source arrays by position without guessing item IDs."""
    try:
        report = build_item_receipt_layout(
            registry_path or "data/extracted/manifest.json"
        )
    except (AssetLoadError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    if output is None:
        click.echo(rendered, nl=False)
        return

    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc

    click.echo(
        f"Wrote {report['entry_count']} joined receive-item records and "
        f"{report['dungeon_mask_count']} separate dungeon masks to {output}"
    )


@cli.command(name="validate-source-export")
@click.argument(
    "source_export",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
def validate_source_export_command(source_export: Path) -> None:
    """Validate a source-inspection JSON export before using it."""
    try:
        payload = load_source_export(source_export)
    except AssetLoadError as exc:
        raise click.ClickException(str(exc)) from exc

    if payload["format"] == MIXED_DATA_TABLE_FORMAT:
        record_count = payload["record_count"]
        record_label = "records"
    elif payload["format"] == "zelda-suite-pointer-table":
        record_count = payload["entry_count"]
        record_label = "entries"
    elif payload["format"] == "zelda-suite-incbin-inventory":
        record_count = payload["declaration_count"]
        record_label = "declarations"
    else:
        record_count = payload["entry_count"]
        record_label = "entries"

    click.echo(
        f"[OK] {payload['format']} v{payload['format_version']}: "
        f"{record_count} {record_label} ({source_export})"
    )



@cli.command(name="audit-overworld-payload-layout")
@click.argument(
    "inventories",
    nargs=-1,
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write JSON to a new file instead of stdout; existing files are preserved.",
)
def audit_overworld_payload_layout_command(
    inventories: tuple[Path, ...],
    output: Path | None,
) -> None:
    """Report paired High/Low source annotations and unresolved range-size discrepancies."""
    try:
        payloads = [load_source_export(path) for path in inventories]
        report = audit_overworld_payload_layout(payloads)
    except (AssetLoadError, OverworldPayloadPairError) as exc:
        raise click.ClickException(str(exc)) from exc

    rendered = json.dumps(
        report,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
        return
    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc

    summary = report["summary"]
    click.echo(
        f"Wrote overworld payload layout audit to {output}; "
        f"pairs={summary['screen_pair_count']}, "
        f"range_mismatches={summary['range_size_mismatch_count']}, "
        f"range_unknown={summary['range_size_unknown_count']}, "
        f"source_ranges_nonadjacent={summary['candidate_source_ranges_nonadjacent_count']}"
    )


@cli.command(name="validate-overworld-payload-pairs")
@click.argument(
    "inventories",
    nargs=-1,
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
def validate_overworld_payload_pairs_command(inventories: tuple[Path, ...]) -> None:
    """Validate exactly one High and Low payload declaration per source screen."""
    try:
        payloads = [load_source_export(path) for path in inventories]
        report = validate_overworld_payload_pairs(payloads)
    except (AssetLoadError, OverworldPayloadPairError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(
        json.dumps(
            report,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
    )


@cli.command(name="migrate-project")
@click.argument(
    "database",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "--json",
    "json_path",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="JSON export path (defaults to the database path with a .json suffix).",
)
def migrate_project_command(database: Path, json_path: Path | None) -> None:
    """Migrate a project database to the current schema and refresh its JSON export."""
    try:
        migrated = migrate_project(database, json_path)
    except (ValueError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc

    if migrated:
        click.echo(f"Migrated project to schema v{2}: {database}")
    else:
        click.echo(f"Project already uses the current schema; refreshed export: {database}")


@cli.command(name="import-source-asset")
@click.argument(
    "database",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.argument("asset_key")
@click.argument(
    "source_export",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "--replace",
    "replace_existing",
    is_flag=True,
    help="Replace an existing asset with this key instead of refusing the duplicate.",
)
def import_source_asset_command(
    database: Path,
    asset_key: str,
    source_export: Path,
    replace_existing: bool,
) -> None:
    """Import a validated source-export JSON file into the SQLite project."""
    try:
        record = import_source_asset(
            database, asset_key, source_export, replace_existing=replace_existing
        )
    except (ValueError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc

    summary = {key: value for key, value in record.items() if key != "payload"}
    click.echo(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


@cli.command(name="import-extracted-asset")
@click.argument(
    "database",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.argument("asset_name")
@click.option(
    "--registry",
    "registry_path",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
    default=None,
    help="Manifest path (defaults to data/extracted/manifest.json).",
)
@click.option("--asset-key", default=None, help="Project-local key (defaults to asset name).")
@click.option(
    "--replace",
    "replace_existing",
    is_flag=True,
    help="Replace an existing project asset under the selected key.",
)
def import_extracted_asset_command(
    database: Path,
    asset_name: str,
    registry_path: Path | None,
    asset_key: str | None,
    replace_existing: bool,
) -> None:
    """Import a committed asset by its validated manifest name."""
    try:
        record = import_extracted_asset(
            database,
            asset_name,
            registry_path or "data/extracted/manifest.json",
            asset_key=asset_key,
            replace_existing=replace_existing,
        )
    except (ValueError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc

    summary = {key: value for key, value in record.items() if key != "payload"}
    click.echo(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


@cli.command(name="list-source-assets")
@click.argument(
    "database",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
def list_source_assets_command(database: Path) -> None:
    """List imported source asset metadata in a project database."""
    try:
        assets = list_source_assets(database)
    except (ValueError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(assets, ensure_ascii=False, indent=2, sort_keys=True))


@cli.command(name="get-source-asset")
@click.argument(
    "database",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.argument("asset_key")
def get_source_asset_command(database: Path, asset_key: str) -> None:
    """Print one imported, validated source asset and its provenance."""
    try:
        record = get_source_asset(database, asset_key)
    except (KeyError, ValueError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True))


@cli.command(name="init")
@click.argument("name")
@click.option(
    "--workspace",
    type=click.Path(path_type=Path, exists=True, file_okay=False, dir_okay=True),
    default=".",
    show_default=True,
    help="Workspace root; project files are created in workspace/project/.",
)
def init_project(name: str, workspace: Path) -> None:
    """Initialize a versioned SQLite project and its JSON export."""
    try:
        database_path, json_path = initialize_project(name, workspace / "project")
    except (ValueError, FileExistsError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Created SQLite project: {database_path}")
    click.echo(f"Created JSON export:    {json_path}")
    click.echo(
        "No ROM was read or copied. Validated source exports can be imported; "
        "semantic game-system schemas and ROM writing remain future work."
    )


@cli.command(name="validate")
@click.argument(
    "database",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
)
@click.option(
    "--json",
    "json_path",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="JSON export path (defaults to the database path with a .json suffix).",
)
def validate(database: Path, json_path: Path | None) -> None:
    """Validate a project's SQLite database and its JSON export without changing either."""
    problems = validate_project(database, json_path)
    if problems:
        for problem in problems:
            click.echo(f"[FAIL] {problem}", err=True)
        raise click.exceptions.Exit(1)

    click.echo(f"[OK] SQLite project and JSON export are consistent: {database}")


@cli.command()
@click.option(
    "--workspace",
    type=click.Path(path_type=Path, exists=True, file_okay=False, dir_okay=True),
    default=".",
    show_default=True,
    help="Workspace root containing base_game_roms/.",
)
def doctor(workspace: Path) -> None:
    """Check the base ROM and report whether Phase 0 tools are on PATH."""
    rom_path = workspace / "base_game_roms" / US_ROM_FILENAME
    status, message = _inspect_base_rom(rom_path)
    click.echo(f"[{status}] Base ROM: {message}")

    rom_check_failed = status != "OK"
    for executable, label in TOOL_CHECKS:
        location = shutil.which(executable)
        if location:
            click.echo(f"[OK] {label}: {location}")
        else:
            click.echo(f"[WARN] {label}: {executable!r} not found on PATH.")

    click.echo(
        "Note: tool checks only verify PATH visibility; they do not run the tools "
        "or prove ROM compatibility."
    )

    if rom_check_failed:
        click.echo(
            "Place a clean, headerless US dump at the path shown above. "
            "Keep ROM files local and do not commit them."
        )
        raise click.exceptions.Exit(1)

    click.echo("Base ROM check passed. Tool warnings are advisory during setup.")
