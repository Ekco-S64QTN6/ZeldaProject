"""Tests for ROM-independent audit of unresolved source-table expressions."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.source_expression_audit import audit_unresolved_table_expressions

ROOT = Path(__file__).resolve().parents[1]
REGISTERED_MANIFEST = ROOT / "data" / "extracted" / "manifest.json"
PINNED_SOURCE_REVISION = "347c23f9fc019c72d32da537c9cb235f468d021d"


def _write_registry(tmp_path: Path) -> Path:
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    assets = []
    specs = [
        ("fixture-values", "BankA.asm", ".values", "db", [("$42", 0x42), ("-5", None)], 0x100),
        ("fixture-symbols", "BankB.asm", ".symbols", "dw", [
            ("SomeLabel", None),
            ("SomeLabel+$10", None),
            ("SomeMacro(SomeLabel)", None),
            ("!CUSTOM_VALUE", None),
        ], 0x200),
    ]

    for name, source_file, table_label, directive, records, start_offset in specs:
        stride = {"db": 1, "dw": 2, "dl": 3}[directive]
        entries = [{
            "table_index": index,
            "entry_file_offset": start_offset + index * stride,
            "source_line": index + 2,
            "source_label": table_label,
            "expression": expression,
            "literal_value": value,
            "source_revision": "synthetic-revision",
        } for index, (expression, value) in enumerate(records)]
        payload = {
            "format": "zelda-suite-data-table",
            "format_version": 1,
            "source_file": source_file,
            "source_revision": "synthetic-revision",
            "parent_label": "Fixture",
            "table_label": table_label,
            "end_label": None,
            "table_file_offset": start_offset,
            "directive": directive,
            "entry_width": stride,
            "entry_count": len(entries),
            "entries": entries,
        }
        filename = f"{name}.json"
        (extracted / filename).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        assets.append({
            "name": name,
            "file": filename,
            "format": "zelda-suite-data-table",
            "source_revision": "synthetic-revision",
            "record_count": len(entries),
            "subsystem": "test",
            "description": "Synthetic source-expression audit input.",
        })

    registry_path = extracted / "manifest.json"
    registry_path.write_text(json.dumps({
        "format": "zelda-suite-asset-registry",
        "format_version": 1,
        "assets": assets,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return registry_path


def test_audit_classifies_unresolved_expressions_without_a_rom(tmp_path: Path) -> None:
    registry = _write_registry(tmp_path)
    report = audit_unresolved_table_expressions(registry)

    assert report["format"] == "zelda-suite-source-expression-audit"
    assert report["format_version"] == 1
    assert report["evidence"] == {
        "source_only": True,
        "rom_bytes_read": False,
        "assembler_expressions_evaluated": False,
    }
    assert report["summary"] == {
        "table_asset_count": 2,
        "entry_count": 6,
        "direct_numeric_entry_count": 1,
        "signed_decimal_entry_count": 1,
        "unresolved_expression_count": 4,
        "classification_counts": {
            "symbol": 1,
            "symbol_with_numeric_addend": 1,
            "compound_or_assembler_specific": 1,
            "other": 1,
        },
    }
    unresolved = report["unresolved_expressions"]
    assert [entry["expression"] for entry in unresolved] == [
        "SomeLabel", "SomeLabel+$10", "SomeMacro(SomeLabel)", "!CUSTOM_VALUE"
    ]
    assert [entry["classification"] for entry in unresolved] == [
        "symbol", "symbol_with_numeric_addend", "compound_or_assembler_specific", "other"
    ]
    assert all(entry["reason"].endswith("it was not evaluated.") for entry in unresolved)
    assert report == audit_unresolved_table_expressions(registry)


def test_audit_cli_writes_report_and_supports_fail_on_unresolved(tmp_path: Path) -> None:
    registry = _write_registry(tmp_path)
    output = tmp_path / "expressions.json"
    runner = CliRunner()
    written = runner.invoke(cli, [
        "audit-unresolved-table-expressions", "--registry", str(registry), "--output", str(output)
    ])
    assert written.exit_code == 0, written.output
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["summary"]["unresolved_expression_count"] == 4
    assert "unresolved=4" in written.output

    failed = runner.invoke(cli, [
        "audit-unresolved-table-expressions", "--registry", str(registry), "--fail-on-unresolved"
    ])
    assert failed.exit_code == 1
    assert json.loads(failed.output)["summary"]["unresolved_expression_count"] == 4


def test_audit_cli_refuses_to_overwrite_output(tmp_path: Path) -> None:
    registry = _write_registry(tmp_path)
    output = tmp_path / "expressions.json"
    output.write_text("do not replace", encoding="utf-8")
    result = CliRunner().invoke(cli, [
        "audit-unresolved-table-expressions", "--registry", str(registry), "--output", str(output)
    ])
    assert result.exit_code != 0
    assert "refusing to overwrite existing output" in result.output
    assert output.read_text(encoding="utf-8") == "do not replace"


def test_audit_pins_current_registered_scalar_table_baseline() -> None:
    """Keep the committed table inventory and unresolved-expression coverage visible."""
    report = audit_unresolved_table_expressions(REGISTERED_MANIFEST)

    assert [asset["asset_name"] for asset in report["assets"]] == [
        "crystal-switch-palette-selectors",
        "falling-prize-delay-timers",
        "falling-prize-fall-heights",
        "falling-prize-item-values",
        "falling-prize-x-offsets",
        "falling-prize-y-offsets",
        "item-receipt-dungeon-masks",
        "item-receipt-graphics-indices",
        "item-receipt-properties",
        "item-receipt-target-addresses",
        "item-receipt-values",
        "item-receipt-wide-flags",
        "item-receipt-x-offsets",
        "item-receipt-y-offsets",
        "mad-batter-pseudo-attack-palettes",
        "text-dictionary-pointers",
    ]
    assert all(asset["source_revision"] == PINNED_SOURCE_REVISION for asset in report["assets"])
    assert report["summary"] == {
        "table_asset_count": 16,
        "entry_count": 689,
        "direct_numeric_entry_count": 514,
        "signed_decimal_entry_count": 77,
        "unresolved_expression_count": 98,
        "classification_counts": {
            "symbol": 98,
            "symbol_with_numeric_addend": 0,
            "compound_or_assembler_specific": 0,
            "other": 0,
        },
    }
    assert {
        asset["asset_name"]: asset["unresolved_expression_count"]
        for asset in report["assets"]
        if asset["unresolved_expression_count"]
    } == {"text-dictionary-pointers": 98}
    assert {
        asset["asset_name"]: asset["signed_decimal_entry_count"]
        for asset in report["assets"]
        if asset["signed_decimal_entry_count"]
    } == {
        "item-receipt-properties": 1,
        "item-receipt-y-offsets": 76,
    }
    assert report["evidence"] == {
        "source_only": True,
        "rom_bytes_read": False,
        "assembler_expressions_evaluated": False,
    }
    assert report == audit_unresolved_table_expressions(REGISTERED_MANIFEST)
