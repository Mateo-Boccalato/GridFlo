"""
GridFlow Lexer
Scans a .gf source file and produces a list of Token objects,
each tagged with its type, label, and (row, col) grid position.
"""

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional


class TokenType(Enum):
    # I/O
    INPUT_PORT  = auto()   # name:type >
    OUTPUT_PORT = auto()   # < name:type
    CONSTANT    = auto()   # *value

    # Cells
    TRANSFORM   = auto()   # [label]
    GATE        = auto()   # ?
    INVERT      = auto()   # !
    COUNTER     = auto()   # #
    DELAY       = auto()   # ~
    COLLECT     = auto()   # {collect}
    REDUCE      = auto()   # (label)
    LATCH       = auto()   # [@]

    # Wires
    WIRE_H      = auto()   # ─  or -
    WIRE_V      = auto()   # │  or |
    CORNER      = auto()   # ┐ ┘ └ ┌
    JUNCTION    = auto()   # ┤ ├ ┬ ┴ ┼ +
    TAP         = auto()   # ·  or .

    # Structure
    PLATE_DEF   = auto()   # plate <name>:
    PLATE_END   = auto()   # end
    FEEDBACK    = auto()   # [@] already covered — loop back marker


@dataclass
class Token:
    type:    TokenType
    label:   str            # raw text content
    row:     int
    col:     int
    # For typed ports, parsed out of "name:type"
    port_name: Optional[str] = None
    port_type: Optional[str] = None  # value | stream | signal | bag
    end_col:   Optional[int] = None  # exclusive end column in the source grid


# ── Wire characters ────────────────────────────────────────────────────────────
WIRE_H_CHARS   = set("─—-\u2500")
WIRE_V_CHARS   = set("│|")
CORNER_CHARS   = set("┐┘└┌\u2510\u2518\u2514\u250C")
JUNCTION_CHARS = set("┤├┬┴┼+\u2524\u251C\u252C\u2534\u253C")
TAP_CHARS      = set("·.\u00B7")


def _parse_port_label(raw: str):
    """Split 'name:type' into (name, type). Type defaults to 'value'."""
    raw = raw.strip()
    if ":" in raw:
        name, ptype = raw.split(":", 1)
        return name.strip(), ptype.strip().lower()
    return raw, "value"


def lex(source: str) -> List[Token]:
    """
    Walk every character in the source grid.
    Return a flat list of Tokens in (row, col) order.
    """
    tokens: List[Token] = []
    lines = source.splitlines()

    i = 0  # line index
    while i < len(lines):
        line = lines[i]

        # ── Plate definition header ────────────────────────────────────────
        m = re.match(r"^\s*plate\s+(\w+)\s*:", line)
        if m:
            tokens.append(Token(TokenType.PLATE_DEF, m.group(1), i, m.start(), m.group(1),
                                end_col=m.end()))
            i += 1
            continue

        # ── Plate end ──────────────────────────────────────────────────────
        if re.match(r"^\s*end\s*$", line):
            tokens.append(Token(TokenType.PLATE_END, "end", i, 0, end_col=len(line)))
            i += 1
            continue

        # ── Scan character by character ────────────────────────────────────
        j = 0
        while j < len(line):
            ch = line[j]

            # Skip spaces
            if ch == " ":
                j += 1
                continue

            # ── Input port:  label:type >  ─────────────────────────────────
            m = re.match(r"([\w:]+)\s*>", line[j:])
            if m and ">" in m.group(0):
                raw = m.group(1)
                name, ptype = _parse_port_label(raw)
                t = Token(TokenType.INPUT_PORT, raw, i, j)
                t.port_name = name
                t.port_type = ptype
                t.end_col = j + len(m.group(0))
                tokens.append(t)
                j += len(m.group(0))
                continue

            # ── Output port:  < label:type  ───────────────────────────────
            if ch == "<":
                rest = line[j+1:].lstrip()
                m = re.match(r"([\w:]+)", rest)
                if m:
                    raw = m.group(1)
                    name, ptype = _parse_port_label(raw)
                    t = Token(TokenType.OUTPUT_PORT, raw, i, j)
                    t.port_name = name
                    t.port_type = ptype
                    t.end_col = j + 1 + (len(line[j+1:]) - len(rest)) + len(m.group(0))
                    tokens.append(t)
                    j += 1 + (len(line[j+1:]) - len(rest)) + len(m.group(0))
                    continue

            # ── Transform cell: [label]  ───────────────────────────────────
            if ch == "[":
                end = line.find("]", j)
                if end != -1:
                    label = line[j+1:end]
                    ttype = TokenType.LATCH if label == "@" else TokenType.TRANSFORM
                    tokens.append(Token(ttype, label, i, j, end_col=end + 1))
                    j = end + 1
                    continue

            # ── Collect cell: {label}  ────────────────────────────────────
            if ch == "{":
                end = line.find("}", j)
                if end != -1:
                    tokens.append(Token(TokenType.COLLECT, line[j+1:end], i, j,
                                        end_col=end + 1))
                    j = end + 1
                    continue

            # ── Reduce cell: (label)  ─────────────────────────────────────
            if ch == "(":
                end = line.find(")", j)
                if end != -1:
                    tokens.append(Token(TokenType.REDUCE, line[j+1:end], i, j,
                                        end_col=end + 1))
                    j = end + 1
                    continue

            # ── Constant: *value or *"quoted string"  ─────────────────────
            if ch == "*":
                # Quoted string constant: *"hello world"
                m = re.match(r'\*"([^"]*)"', line[j:])
                if m:
                    tokens.append(Token(TokenType.CONSTANT, m.group(1), i, j,
                                        end_col=j + len(m.group(0))))
                    j += len(m.group(0))
                    continue
                # Unquoted constant: *42 or *true
                m = re.match(r"\*([A-Za-z0-9_.]+)", line[j:])
                if m:
                    tokens.append(Token(TokenType.CONSTANT, m.group(1), i, j,
                                        end_col=j + len(m.group(0))))
                    j += len(m.group(0))
                    continue

            # ── Single-char control cells ─────────────────────────────────
            if ch == "?":
                tokens.append(Token(TokenType.GATE,    "?", i, j, end_col=j + 1)); j += 1; continue
            if ch == "!":
                tokens.append(Token(TokenType.INVERT,  "!", i, j, end_col=j + 1)); j += 1; continue
            if ch == "#":
                tokens.append(Token(TokenType.COUNTER, "#", i, j, end_col=j + 1)); j += 1; continue
            if ch == "~":
                tokens.append(Token(TokenType.DELAY,   "~", i, j, end_col=j + 1)); j += 1; continue

            # ── Wire characters ───────────────────────────────────────────
            if ch in WIRE_H_CHARS:
                tokens.append(Token(TokenType.WIRE_H,   ch, i, j, end_col=j + 1)); j += 1; continue
            if ch in WIRE_V_CHARS:
                tokens.append(Token(TokenType.WIRE_V,   ch, i, j, end_col=j + 1)); j += 1; continue
            if ch in CORNER_CHARS:
                tokens.append(Token(TokenType.CORNER,   ch, i, j, end_col=j + 1)); j += 1; continue
            if ch in JUNCTION_CHARS:
                tokens.append(Token(TokenType.JUNCTION, ch, i, j, end_col=j + 1)); j += 1; continue
            if ch in TAP_CHARS:
                tokens.append(Token(TokenType.TAP,      ch, i, j, end_col=j + 1)); j += 1; continue

            # Unknown character — skip silently
            j += 1

        i += 1

    return tokens
