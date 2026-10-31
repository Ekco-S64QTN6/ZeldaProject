"""Tests for message decoding (src/zelda_suite/extract/text_decode.py).

Source-only tests run in CI from the pinned disassembly; the ROM tests run only when the
local US image is present.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.extract.text_decode import (
    ATTESTED_GLYPHS,
    COMMANDS,
    Dictionary,
    TextDecodeError,
    decode_markup,
    decode_text_messages,
    display_text,
    encode_markup,
    rom_dictionary,
    source_dictionary,
    split_block_marker,
    tokens,
)
from zelda_suite.extract.text_message_byte_verification import (
    default_text_message_source_blocks,
    parse_source_message_bytes,
)

ROOT = Path(__file__).resolve().parents[1]
DISASM = ROOT / "reference" / "AsarUSALTTPDisassembly"
US_ROM = ROOT / "base_game_roms" / "Legend of Zelda, The - A Link to the Past (U) [!].smc"


@pytest.fixture(scope="module")
def sources() -> tuple[str, str]:
    if not (DISASM / "Bank1C.asm").is_file():
        pytest.skip("disassembly submodule not checked out")
    return (DISASM / "Bank1C.asm").read_text(encoding="utf-8"), (DISASM / "Bank0E.asm").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def rom() -> bytes:
    if not US_ROM.is_file():
        pytest.skip("local US ROM not present (CI is ROM-independent)")
    return US_ROM.read_bytes()


def test_the_glyph_map_agrees_with_every_annotated_source_line(sources: tuple[str, str]) -> None:
    """Re-derive glyph meanings from the source annotations: each attested glyph is the
    majority reading of its byte, and only the known $25 'L' typo disagrees."""
    main, extra = sources
    db = re.compile(r"^\s*db\s+(?P<v>(?:\$[0-9A-Fa-f]{2}\s*,?\s*)+);\s?(?P<c>.*)$")
    votes: dict[int, Counter] = {}
    for text in (main, extra[extra.index("Message_DataExtra"):]):
        for line in text.splitlines():
            m = db.match(line)
            if not m:
                continue
            vals = [int(x, 16) for x in re.findall(r"\$([0-9A-Fa-f]{2})", m["v"])]
            if any(0x67 <= v < 0x80 for v in vals):
                continue
            toks = re.findall(r"\[[^\]]*\]|.", m["c"].rstrip())
            if len(toks) != len(vals):
                continue
            for v, t in zip(vals, toks):
                if v < 0x67:
                    votes.setdefault(v, Counter())[t] += 1
    disagreements = {v: dict(c) for v, c in votes.items() if len(c) > 1}
    assert disagreements == {0x25: {"l": 1211, "L": 1}}
    for v, c in votes.items():
        expected = " " if c.most_common(1)[0][0] == "⎵" else c.most_common(1)[0][0]
        assert ATTESTED_GLYPHS[v] == expected, f"${v:02X}"
    assert set(votes) == set(ATTESTED_GLYPHS)


def test_every_message_decodes_and_encodes_back_to_its_bytes(sources: tuple[str, str]) -> None:
    main, extra = sources
    dictionary = source_dictionary(extra)
    messages = parse_source_message_bytes(default_text_message_source_blocks(main, extra))
    assert len(messages) == 397
    for m in messages:
        message, marker = split_block_marker(m["data"])
        assert encode_markup(decode_markup(message, dictionary), dictionary) + marker == m["data"], m["message_label"]
    last_main = next(m for m in messages if m["message_label"] == "Message_0166")
    assert split_block_marker(last_main["data"])[1] == b"\x80"


def test_a_known_message_reads_as_its_annotation(sources: tuple[str, str]) -> None:
    report = decode_text_messages(*sources, message_id=3)
    (m,) = report["messages"]
    assert m["markup"] == "{Speed 00}Save And C[on]t[in]ue{Line2}Save And Qu[it]{Line3}Do Not Save And C[on]t[in]ue"
    assert m["text"] == "Save And Continue\nSave And Quit\nDo Not Save And Continue"


def test_the_source_leaves_dot_you_unresolved(sources: tuple[str, str]) -> None:
    dictionary = source_dictionary(sources[1])
    assert dictionary.entries[96] is None and all(e for i, e in enumerate(dictionary.entries) if i != 96)
    report = decode_text_messages(*sources)
    assert report["findings"] == [{"code": "dictionary_entry_unresolved_in_source", "entry": 96,
                                   "resolved_from_rom": False, "rom_bytes": None}]


def test_malformed_bytes_are_refused() -> None:
    d = Dictionary([bytes([0x00])] * 97)
    with pytest.raises(TextDecodeError, match="no End"):
        tokens(bytes([0x00, 0x01]))
    with pytest.raises(TextDecodeError, match="neither"):
        tokens(bytes([0x84, 0x7F]))
    with pytest.raises(TextDecodeError, match="parameter"):
        tokens(bytes([0x7A]))
    with pytest.raises(TextDecodeError, match="after the end"):
        tokens(bytes([0x7F, 0x00]))
    with pytest.raises(TextDecodeError, match="no glyph"):
        encode_markup("é", d)
    with pytest.raises(TextDecodeError, match="takes 1"):
        encode_markup("{Speed}", d)


def test_parameters_that_look_like_end_are_parameters() -> None:
    d = Dictionary([bytes([0x00])] * 97)
    data = bytes([0x7A, 0x7F, 0x00, 0x7F])            # Speed $7F, 'A', End
    assert decode_markup(data, d) == "{Speed 7F}A" and encode_markup("{Speed 7F}A", d) == data
    assert all(n in (0, 1) for _, n in COMMANDS.values())


def test_the_rom_dictionary_resolves_dot_you(rom: bytes, sources: tuple[str, str]) -> None:
    d = rom_dictionary(rom)
    assert d.entries[96] == bytes([0x18, 0x28, 0x2E]) and d.text(96) == "You"
    src = source_dictionary(sources[1])
    assert all(src.entries[i] == d.entries[i] for i in range(97) if i != 96)


def test_every_rom_message_decodes_from_rom_bytes(rom: bytes, sources: tuple[str, str]) -> None:
    report = decode_text_messages(*sources, rom)
    assert report["message_count"] == 397 and report["rom_bytes_read"]
    assert not any("{dict" in m["markup"] for m in report["messages"])
    d = rom_dictionary(rom)
    for m in report["messages"]:
        end = m["file_offset"] + m["byte_count"]
        assert encode_markup(m["markup"], d) == rom[m["file_offset"]:end], m["message_label"]
    help_me = next(m for m in report["messages"] if m["message_id"] == 0x20)
    assert help_me["text"].startswith("Help me…\nI am in the dungeon of the\ncastle.")


def test_display_text_names_the_player() -> None:
    d = Dictionary([bytes([0x00])] * 97)
    assert display_text(bytes([0x6A, 0x3E, 0x7F]), d) == "<Name>!"


def test_the_cli_prints_text_and_writes_json(sources: tuple[str, str], tmp_path: Path) -> None:
    runner = CliRunner()
    text = runner.invoke(cli, ["decode-text-messages", "--message-id", "3", "--text",
                               "--main-source", str(DISASM / "Bank1C.asm"),
                               "--extra-source", str(DISASM / "Bank0E.asm")])
    assert text.exit_code == 0, text.output and "Save And Quit" in text.output
    out = tmp_path / "messages.json"
    wrote = runner.invoke(cli, ["decode-text-messages", "--output", str(out),
                                "--main-source", str(DISASM / "Bank1C.asm"),
                                "--extra-source", str(DISASM / "Bank0E.asm")])
    assert wrote.exit_code == 0, wrote.output and out.is_file()
    again = runner.invoke(cli, ["decode-text-messages", "--output", str(out),
                                "--main-source", str(DISASM / "Bank1C.asm"),
                                "--extra-source", str(DISASM / "Bank0E.asm")])
    assert again.exit_code != 0 and "exists" in again.output
