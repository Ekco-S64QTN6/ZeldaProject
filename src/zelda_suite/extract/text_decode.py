"""Decode ALttP message bytes into readable text and a lossless markup.

The grammar is the pinned consumer's (`Text_LoadCharacterBuffer`, Bank0E.asm):

- a byte below `$67` is a glyph;
- `$67–$7F` is a command (`Text_Command` jump table); `$6B–$6E` and `$77–$7A` take the
  next byte as a parameter; `$7F` ends the message;
- a byte of `$88` or more is dictionary entry `byte - $88`, copied from
  `Text_DictionaryPointers[i]` up to (not including) `[i + 1]`
  (`Text_DictionarySequence`).

Glyph meanings come from the disassembly's own annotations: every `db` line of the two
message blocks whose comment renders its bytes was aligned byte-for-byte (5,044 lines);
each glyph below maps to one character on every line it appears (`$25` once reads "L"
against 1,211 "l" — an annotation typo). `X`, `4`, `6`, `7` and `9` never appear in an
annotated line; they are **inferred** from the alphabet and digit order and reported as
such. Bytes with no evidence are written `{glyph XX}`.

Markup (lossless: `encode_markup(decode_markup(b)) == b`):

- glyphs as their character; a glyph shared by several bytes (the heart pieces) or
  without a character as `{glyph XX}`;
- dictionary entries as `[text]`, as the source annotations write them (all 97 entry
  texts are distinct);
- commands as `{Name}` or `{Name XX}`; the final `{End}` is implied.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

GLYPH_LIMIT = 0x67
DICTIONARY_BASE = 0x88
END = 0x7F
SPACE = 0x59
DICTIONARY_POINTER_TABLE_OFFSET = 0x074703      # $0E:C703, 98 words incl. the end sentinel
DICTIONARY_POINTER_COUNT = 98
DICTIONARY_ENTRY_COUNT = DICTIONARY_POINTER_COUNT - 1

_ALPHA = {i: chr(ord("A") + i) for i in range(26)} | {0x1A + i: chr(ord("a") + i) for i in range(26)}
_DIGITS = {0x34 + i: str(i) for i in range(10)}
#: From the annotations (see module docstring).
ATTESTED_GLYPHS: dict[int, str] = {
    **{b: c for b, c in _ALPHA.items() if b != 0x17},
    **{b: c for b, c in _DIGITS.items() if b not in (0x38, 0x3A, 0x3B, 0x3D)},
    0x3E: "!", 0x3F: "?", 0x40: "-", 0x41: ".", 0x42: ",", 0x43: "…", 0x44: ">",
    0x45: "(", 0x46: ")", 0x47: "☥", 0x48: "𓈗", 0x49: "Ƨ", 0x4C: '"',
    0x4D: "↑", 0x4E: "↓", 0x4F: "←", 0x50: "→", 0x51: "'",
    **{b: "♥" for b in range(0x52, 0x59)},
    SPACE: " ", 0x5B: "Ⓐ", 0x5C: "Ⓑ", 0x5D: "ⓧ", 0x5E: "ⓨ",
}
#: Never annotated; placed by alphabet/digit order.
INFERRED_GLYPHS: dict[int, str] = {0x17: "X", 0x38: "4", 0x3A: "6", 0x3B: "7", 0x3D: "9"}
GLYPHS: dict[int, str] = {**ATTESTED_GLYPHS, **INFERRED_GLYPHS}

#: Command byte -> (name, parameter bytes), names from the `Text_Command` table comments.
COMMANDS: dict[int, tuple[str, int]] = {
    0x67: ("NextPic", 0), 0x68: ("Choose", 0), 0x69: ("Item", 0), 0x6A: ("Name", 0),
    0x6B: ("Window", 1), 0x6C: ("Number", 1), 0x6D: ("Position", 1), 0x6E: ("ScrollSpd", 1),
    0x6F: ("SelChng", 0), 0x70: ("Crash", 0), 0x71: ("Choose2", 0), 0x72: ("Choose3", 0),
    0x73: ("Scroll", 0), 0x74: ("Line1", 0), 0x75: ("Line2", 0), 0x76: ("Line3", 0),
    0x77: ("Color", 1), 0x78: ("Wait", 1), 0x79: ("Sound", 1), 0x7A: ("Speed", 1),
    0x7B: ("Command7B", 0), 0x7C: ("Command7C", 0), 0x7D: ("Command7D", 0), 0x7E: ("WaitKey", 0),
    0x7F: ("End", 0),
}
_COMMAND_BYTES = {name: byte for byte, (name, _) in COMMANDS.items()}
_SHARED = {c for c in GLYPHS.values() if list(GLYPHS.values()).count(c) > 1}
_MARKUP_CHAR = {b: c for b, c in GLYPHS.items() if c not in _SHARED}
_CHAR_BYTE = {c: b for b, c in _MARKUP_CHAR.items()}


class TextDecodeError(ValueError):
    """Bytes that are not a well-formed message, or markup that does not encode."""


@dataclass(frozen=True)
class Dictionary:
    """The 97 entries' glyph bytes (None where unresolved) and their texts."""

    entries: list[bytes | None]

    def text(self, index: int) -> str | None:
        data = self.entries[index]
        if data is None:
            return None
        return "".join(_MARKUP_CHAR.get(b) or f"{{glyph {b:02X}}}" for b in data)

    def index_of(self, text: str) -> int:
        for i in range(len(self.entries)):
            if self.text(i) == text:
                return i
        raise TextDecodeError(f"[{text}] is not a dictionary entry")


def rom_dictionary(rom: bytes) -> Dictionary:
    """The dictionary as the game reads it: each entry from its pointer to the next."""
    words = [int.from_bytes(rom[DICTIONARY_POINTER_TABLE_OFFSET + 2 * i:DICTIONARY_POINTER_TABLE_OFFSET + 2 * i + 2],
                            "little") for i in range(DICTIONARY_POINTER_COUNT)]
    if any(not 0x8000 <= w <= 0xFFFF for w in words) or any(a >= b for a, b in zip(words, words[1:])):
        raise TextDecodeError("the dictionary pointer table is not 98 increasing bank-$0E addresses")
    offset = lambda w: 0x070000 + (w - 0x8000)          # LoROM bank $0E
    return Dictionary([rom[offset(words[i]):offset(words[i + 1])] for i in range(DICTIONARY_ENTRY_COUNT)])


_SOURCE_ENTRY_RE = re.compile(r"^\s*\.(?P<label>\w+)\s*$")
_SOURCE_DB_RE = re.compile(r"^\s*(?P<dir>db|dw|dl)\s+(?P<vals>[^;]*)", re.IGNORECASE)


def source_dictionary(bank0e_source: str) -> Dictionary:
    """The dictionary from the pinned source's `DictionaryEntries` block. An entry not
    declared with `db` (`.You` is written `dw $18, $28, $2E`) is left unresolved (None):
    the source does not say which bytes it means; `rom_dictionary` does."""
    lines = bank0e_source.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "DictionaryEntries:")
    entries: list[bytes | None] = []
    current: bytearray | None = None
    unresolved = False
    for line in lines[start + 1:]:
        code = line.split(";", 1)[0]
        if code.strip() == "}":
            break
        if (m := _SOURCE_ENTRY_RE.match(code)):
            if current is not None:
                entries.append(None if unresolved else bytes(current))
            if m["label"] == "endOfTable":
                current = None
                break
            current, unresolved = bytearray(), False
        elif (m := _SOURCE_DB_RE.match(code)) and current is not None:
            if m["dir"].lower() != "db":
                unresolved = True
            current += bytes(int(v, 16) for v in re.findall(r"\$([0-9A-Fa-f]{1,2})\b", m["vals"]))
    if len(entries) != DICTIONARY_ENTRY_COUNT:
        raise TextDecodeError(f"expected {DICTIONARY_ENTRY_COUNT} dictionary entries, found {len(entries)}")
    return Dictionary(entries)


def tokens(data: bytes) -> list[tuple]:
    """('glyph', b) | ('dict', i) | ('cmd', byte, params) up to and including the End command."""
    out: list[tuple] = []
    i = 0
    while i < len(data):
        b = data[i]
        if b < GLYPH_LIMIT:
            out.append(("glyph", b))
            i += 1
        elif b < 0x80:
            name, n = COMMANDS[b]
            if i + 1 + n > len(data):
                raise TextDecodeError(f"{name} at byte {i} is missing its parameter")
            out.append(("cmd", b, bytes(data[i + 1:i + 1 + n])))
            i += 1 + n
            if b == END:
                if i != len(data):
                    raise TextDecodeError(f"{len(data) - i} byte(s) after the end of the message")
                return out
        elif DICTIONARY_BASE <= b < DICTIONARY_BASE + DICTIONARY_ENTRY_COUNT:
            out.append(("dict", b - DICTIONARY_BASE))
            i += 1
        else:
            raise TextDecodeError(f"byte ${b:02X} at {i} is neither a glyph, a command nor a dictionary entry")
    raise TextDecodeError("the message has no End ($7F)")


def decode_markup(data: bytes, dictionary: Dictionary) -> str:
    parts: list[str] = []
    for t in tokens(data):
        if t[0] == "glyph":
            parts.append(_MARKUP_CHAR.get(t[1]) or f"{{glyph {t[1]:02X}}}")
        elif t[0] == "dict":
            text = dictionary.text(t[1])
            parts.append(f"[{text}]" if text is not None else f"{{dict {t[1]:02X}}}")
        elif t[1] != END:
            name, _ = COMMANDS[t[1]]
            parts.append("{" + name + "".join(f" {p:02X}" for p in t[2]) + "}")
    return "".join(parts)


_MARKUP_RE = re.compile(r"\{(?P<cmd>[^}]*)\}|\[(?P<dict>[^\]]*)\]|(?P<ch>.)", re.DOTALL)


def encode_markup(markup: str, dictionary: Dictionary) -> bytes:
    """Markup back to message bytes, End appended."""
    out = bytearray()
    for m in _MARKUP_RE.finditer(markup):
        if m["ch"] is not None:
            if m["ch"] not in _CHAR_BYTE:
                raise TextDecodeError(f"{m['ch']!r} has no glyph")
            out.append(_CHAR_BYTE[m["ch"]])
        elif m["dict"] is not None:
            out.append(DICTIONARY_BASE + dictionary.index_of(m["dict"]))
        else:
            name, *params = m["cmd"].split()
            if name == "glyph":
                out.append(int(params[0], 16))
            elif name == "dict":
                out.append(DICTIONARY_BASE + int(params[0], 16))
            elif name in _COMMAND_BYTES and name != "End":
                byte = _COMMAND_BYTES[name]
                if len(params) != COMMANDS[byte][1]:
                    raise TextDecodeError(f"{{{name}}} takes {COMMANDS[byte][1]} parameter(s)")
                out += bytes([byte] + [int(p, 16) for p in params])
            else:
                raise TextDecodeError(f"unknown markup {{{m['cmd']}}}")
    out.append(END)
    return bytes(out)


def display_text(data: bytes, dictionary: Dictionary) -> str:
    """Readable text: dictionary expanded, Line2/Line3/Scroll as line breaks, the
    player's name as <Name>, other commands dropped."""
    parts: list[str] = []
    for t in tokens(data):
        if t[0] == "glyph":
            parts.append(GLYPHS.get(t[1], "�"))
        elif t[0] == "dict":
            entry = dictionary.entries[t[1]]
            parts.append("".join(GLYPHS.get(b, "�") for b in entry) if entry is not None else "�")
        elif COMMANDS[t[1]][0] in ("Line2", "Line3", "Scroll"):
            parts.append("\n")
        elif COMMANDS[t[1]][0] == "Name":
            parts.append("<Name>")
    return "".join(parts).strip()


def evidence(data: bytes) -> dict[str, Any]:
    """Which glyphs a message uses on inference or without a meaning."""
    used = {t[1] for t in tokens(data) if t[0] == "glyph"}
    return {"inferred_glyphs": sorted(f"${b:02X}" for b in used & set(INFERRED_GLYPHS)),
            "unknown_glyphs": sorted(f"${b:02X}" for b in used - set(GLYPHS))}


BANK_CHANGE = 0x80          # `db $80 ; Change banks` after the main block's last message
TEXT_MESSAGES_FORMAT = "zelda-suite-text-messages"


def split_block_marker(data: bytes) -> tuple[bytes, bytes]:
    """(message, trailing block marker): the main block's last message is followed by the
    `$80` bank-change marker, which the source index counts with that message."""
    end = data.find(bytes([END]))
    if end != -1 and data[end + 1:] == bytes([BANK_CHANGE]):
        return data[:end + 1], data[end + 1:]
    return data, b""


def decode_text_messages(main_source: str, extra_source: str, rom: bytes | None = None, *,
                         message_id: int | None = None) -> dict[str, Any]:
    """Every message decoded, from the pinned source alone or (with `rom`) from the ROM.

    With a ROM, each message's bytes are read at its sequential offset and must equal the
    source literals (the same check as `verify-text-message-bytes`), and the dictionary is
    read through the ROM's pointer table, which resolves `.You`. Without one, `.You` stays
    unresolved and messages using it show `{dict 60}`.
    """
    from zelda_suite.extract.text_message_byte_verification import (
        default_text_message_source_blocks, parse_source_message_bytes)
    messages = parse_source_message_bytes(default_text_message_source_blocks(main_source, extra_source))
    source_dict = source_dictionary(extra_source)
    dictionary = rom_dictionary(rom) if rom is not None else source_dict
    findings: list[dict[str, Any]] = []
    for i, (s, r) in enumerate(zip(source_dict.entries, dictionary.entries)):
        if s is None:
            findings.append({"code": "dictionary_entry_unresolved_in_source", "entry": i,
                             "resolved_from_rom": r is not None and rom is not None,
                             "rom_bytes": r.hex().upper() if (r is not None and rom is not None) else None})
        elif rom is not None and s != r:
            findings.append({"code": "dictionary_entry_source_rom_mismatch", "entry": i,
                             "source_bytes": s.hex().upper(), "rom_bytes": r.hex().upper()})
    entries = []
    for m in messages:
        if message_id is not None and m["message_id"] != message_id:
            continue
        data = m["data"]
        if rom is not None:
            at = m["sequential_file_offset"]
            rom_data = rom[at:at + len(data)]
            if rom_data != data:
                raise TextDecodeError(f"{m['message_label']}: ROM bytes at ${at:06X} differ from the source")
            data = rom_data
        message, marker = split_block_marker(data)
        entries.append({
            "message_id": m["message_id"], "message_label": m["message_label"],
            "source_file": m["source_file"], "source_line": m["source_line"],
            "file_offset": m["sequential_file_offset"], "byte_count": len(message),
            "markup": decode_markup(message, dictionary),
            "text": display_text(message, dictionary),
            "trailing_block_marker": marker.hex().upper() or None,
            **evidence(message),
        })
    return {
        "format": TEXT_MESSAGES_FORMAT, "format_version": 1,
        "dictionary_source": "rom_pointer_table" if rom is not None else "pinned_source",
        "rom_bytes_read": rom is not None,
        "message_count": len(entries),
        "glyphs": {"attested": len(ATTESTED_GLYPHS), "inferred": sorted(f"${b:02X}" for b in INFERRED_GLYPHS)},
        "dictionary": [{"entry": i, "byte": f"${DICTIONARY_BASE + i:02X}", "text": dictionary.text(i)}
                       for i in range(DICTIONARY_ENTRY_COUNT)],
        "findings": findings,
        "messages": entries,
    }
