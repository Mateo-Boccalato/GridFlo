"""
GridFlow Parser
Takes the flat token list from the lexer and builds a directed CellGraph.
Nodes are Cell objects. Edges are Wire objects carrying type information.
Type-checks all connections before returning the graph.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from lexer import Token, TokenType


# ── Data types ─────────────────────────────────────────────────────────────────

VALID_TYPES = {"value", "stream", "signal", "bag"}
WIRE_TOKEN_TYPES = {
    TokenType.WIRE_H,
    TokenType.WIRE_V,
    TokenType.CORNER,
    TokenType.JUNCTION,
    TokenType.TAP,
}
DOWN_START_TYPES = {
    TokenType.WIRE_V,
    TokenType.CORNER,
    TokenType.JUNCTION,
    TokenType.TAP,
}
STEP_BY_DIRECTION = {
    "right": (0, 1),
    "left": (0, -1),
    "down": (1, 0),
    "up": (-1, 0),
}


class GridFlowTypeError(Exception):
    pass


class GridFlowParseError(Exception):
    pass


# ── Graph nodes ────────────────────────────────────────────────────────────────

@dataclass
class Cell:
    id:       str           # unique id, e.g. "transform_3_10"
    kind:     str           # token type name, e.g. "TRANSFORM"
    token_type: TokenType
    label:    str           # cell label, e.g. "trim"
    row:      int
    col:      int
    end_col:  int           # exclusive end column in the source grid
    # Populated during wiring
    inputs:   List["Wire"] = field(default_factory=list)
    outputs:  List["Wire"] = field(default_factory=list)
    # For I/O ports
    port_name: Optional[str] = None
    port_type: Optional[str] = None
    # For latch cells — marks this as a feedback anchor
    is_latch:  bool = False


@dataclass
class Wire:
    source:    Cell
    target:    Cell
    wire_type: str = "value"   # inferred or declared
    is_feedback: bool = False   # True for [@] return edges
    direction: Optional[str] = None  # right/down branch from the source cell


@dataclass
class CellGraph:
    cells:        List[Cell]         = field(default_factory=list)
    wires:        List[Wire]         = field(default_factory=list)
    input_ports:  List[Cell]         = field(default_factory=list)
    output_ports: List[Cell]         = field(default_factory=list)
    plates:       Dict[str, "CellGraph"] = field(default_factory=dict)


# ── Parser ─────────────────────────────────────────────────────────────────────

class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.graph  = CellGraph()
        # Spatial index: (row, col) → Cell
        self._grid: Dict[Tuple[int,int], Cell] = {}

    def parse(self) -> CellGraph:
        # ── 1. Extract plate definitions ──────────────────────────────────
        main_tokens, plate_groups = self._split_plates()

        for plate_name, plate_tokens in plate_groups.items():
            sub_parser = Parser(plate_tokens)
            sub_graph  = sub_parser.parse()
            self.graph.plates[plate_name] = sub_graph

        # ── 2. Build cells from main token list ───────────────────────────
        self._build_cells(main_tokens)

        # ── 3. Trace wires — connect adjacent cells ───────────────────────
        self._trace_wires()

        # ── 4. Type-check all wires ───────────────────────────────────────
        self._type_check()

        return self.graph

    # ── Phase 1: split plate blocks out of token stream ───────────────────

    def _split_plates(self):
        main_tokens   = []
        plate_groups  = {}
        current_plate = None
        buf           = []

        for tok in self.tokens:
            if tok.type == TokenType.PLATE_DEF:
                current_plate = tok.label
                buf = []
            elif tok.type == TokenType.PLATE_END and current_plate:
                plate_groups[current_plate] = buf
                current_plate = None
                buf = []
            elif current_plate is not None:
                buf.append(tok)
            else:
                main_tokens.append(tok)

        return main_tokens, plate_groups

    # ── Phase 2: instantiate Cell objects, index by position ──────────────

    def _build_cells(self, tokens: List[Token]):
        for tok in tokens:
            # Skip wire characters — they're structural, not cells
            if tok.type in WIRE_TOKEN_TYPES:
                continue

            cell_id = f"{tok.type.name.lower()}_{tok.row}_{tok.col}"
            cell = Cell(
                id        = cell_id,
                kind      = tok.type.name,
                token_type= tok.type,
                label     = tok.label,
                row       = tok.row,
                col       = tok.col,
                end_col   = tok.end_col or tok.col + len(tok.label) + 1,
                is_latch  = (tok.type == TokenType.LATCH),
                port_name = tok.port_name,
                port_type = tok.port_type,
            )

            self.graph.cells.append(cell)
            self._grid[(tok.row, tok.col)] = cell

            if tok.type == TokenType.INPUT_PORT:
                self.graph.input_ports.append(cell)
            elif tok.type == TokenType.OUTPUT_PORT:
                self.graph.output_ports.append(cell)

    # ── Phase 3: wire tracing ──────────────────────────────────────────────
    # Strategy: build a full position map of ALL tokens (including wires),
    # then for each cell token, scan rightward and downward from the
    # first column AFTER the cell's text span. Follow wire characters
    # until hitting another cell token.

    def _token_map(self) -> Dict[Tuple[int,int], Token]:
        return {(t.row, t.col): t for t in self.tokens}

    def _cell_right_edge(self, cell: Cell) -> int:
        """Return the column index just past this cell's rightmost character."""
        return cell.end_col

    def _trace_wires(self):
        tmap = self._token_map()
        visited_edges: Set[Tuple[str,str]] = set()

        for cell in self.graph.cells:
            # Rightward from the first column after the cell text.
            target = self._follow_wire(tmap, cell.row, self._cell_right_edge(cell), "right")
            self._connect_once(cell, target, "right", visited_edges)

            # ── Downward — only follow if there's an actual │ wire below ──
            down_cols = [cell.col]
            right_edge = self._cell_right_edge(cell)
            if right_edge != cell.col:
                down_cols.append(right_edge)

            for down_col in down_cols:
                below_tok = tmap.get((cell.row + 1, down_col))
                if below_tok and below_tok.type in DOWN_START_TYPES:
                    target = self._follow_wire(tmap, cell.row + 1, down_col, "down")
                    self._connect_once(cell, target, "down", visited_edges)

    def _connect_once(
        self,
        source: Cell,
        target: Optional[Cell],
        direction: str,
        visited_edges: Set[Tuple[str, str]],
    ):
        if target is None or target.id == source.id:
            return
        edge_key = (source.id, target.id)
        if edge_key in visited_edges:
            return

        wire = Wire(source=source, target=target, direction=direction)
        self.graph.wires.append(wire)
        source.outputs.append(wire)
        target.inputs.append(wire)
        visited_edges.add(edge_key)

    def _follow_wire(self, tmap, row, col, direction) -> Optional[Cell]:
        """
        Walk along wire/corner/junction tokens from (row, col).
        Returns the first Cell encountered, or None.
        """
        candidates = [(row, col, direction)]
        steps_left = 300

        while candidates and steps_left > 0:
            row, col, direction = candidates.pop()

            while steps_left > 0:
                if row < 0 or col < 0:
                    break

                steps_left -= 1
                tok = tmap.get((row, col))
                if tok is None:
                    break

                # Hit a real cell token — return its Cell object
                if tok.type not in WIRE_TOKEN_TYPES:
                    return self._grid.get((row, col))

                if tok.type == TokenType.CORNER:
                    direction = self._turn(tok.label, direction)
                    if direction is None:
                        break
                    next_row, next_col = self._step(row, col, direction)
                    if direction in ("up", "down"):
                        candidates.append((next_row, next_col + 1, "right"))
                    row, col = next_row, next_col
                    continue

                row, col = self._step(row, col, direction)

        return None

    @staticmethod
    def _step(row, col, direction):
        dr, dc = STEP_BY_DIRECTION[direction]
        return row + dr, col + dc

    def _turn(self, corner_char: str, incoming: str) -> Optional[str]:
        """Map corner character + incoming direction to outgoing direction."""
        turns = {
            ("┐", "right"): "down",  ("┐", "up"):   "left",
            ("┘", "down"):  "left",  ("┘", "right"): "up",
            ("└", "down"):  "right", ("└", "left"):  "up",
            ("┌", "up"):    "right", ("┌", "left"):  "down",
        }
        return turns.get((corner_char, incoming))

    # ── Phase 4: type checking ─────────────────────────────────────────────

    # Rules:
    #   input ports declare their type
    #   types propagate forward through transform cells (value→value)
    #   {collect} : value/stream → bag
    #   (reduce)  : bag → value
    #   ?  gate   : first input is signal, second passes through unchanged
    #   [@] latch : preserves type of its input wire

    _TRANSFORM_IO = {
        # label patterns → (accepted_type, output_type)
        "trim":    ("value", "value"),
        "upper":   ("value", "value"),
        "lower":   ("value", "value"),
        "str":     ("value", "value"),
        "int":     ("value", "value"),
        "float":   ("value", "value"),
        "len":     ("value", "value"),
        "range":   ("value", "stream"),
        "split":   ("value", "stream"),
        "join":    ("bag",   "value"),
        "reverse": ("value", "value"),
        "sum":     ("bag",   "value"),
        "max":     ("bag",   "value"),
        "min":     ("bag",   "value"),
        "count":   ("bag",   "value"),
        "!":       ("value", "value"),
        "not":     ("signal", "signal"),
        "and":     ("signal", "signal"),
        "or":      ("signal", "signal"),
        # Signal-producing comparisons (value → signal, feed into ? gate)
        "?=0":  ("value", "signal"),
        "?=":   ("value", "signal"),
        "?!=":  ("value", "signal"),
        "?>":   ("value", "signal"),
        "?<":   ("value", "signal"),
        "?>=":  ("value", "signal"),
        "?<=":  ("value", "signal"),
    }

    def _infer_wire_type(self, wire: Wire) -> str:
        src = wire.source

        # Input port — type is declared
        if src.kind == "INPUT_PORT":
            return src.port_type or "value"

        # Latch — preserve type of its input
        if src.is_latch:
            if src.inputs:
                return src.inputs[0].wire_type
            return "value"

        # Collect — always outputs bag
        if src.kind == "COLLECT":
            return "bag"

        # Reduce — always outputs value
        if src.kind == "REDUCE":
            return "value"

        # Constant — value
        if src.kind == "CONSTANT":
            return "value"

        # Gate ? — output type mirrors value input type (not signal input)
        if src.kind == "GATE":
            for inp in src.inputs:
                if inp.wire_type != "signal":
                    return inp.wire_type
            return "value"

        # Transform cell — look up in table, or default value→value
        if src.kind == "TRANSFORM":
            label = src.label.lower()
            if label.startswith("map:"):
                return "stream"
            if label.startswith("const:"):
                return "value"
            rule = self._TRANSFORM_IO.get(src.label.lower())
            if rule:
                return rule[1]
            # Signal-producing comparisons: labels starting with ?
            if src.label.startswith("?"):
                return "signal"
            # Arithmetic operators: value → value
            if any(op in src.label for op in ["+", "-", "×", "÷", "%", "^",
                                               "=", "≠", ">", "<", "≥", "≤"]):
                return "value"
            return "value"

        return "value"

    def _type_check(self):
        """
        Propagate types forward through the graph in topological order.
        Raise GridFlowTypeError on any mismatch.
        """
        from collections import deque

        # Compute in-degree for topological sort (skip feedback edges)
        in_degree = {c.id: 0 for c in self.graph.cells}
        for wire in self.graph.wires:
            if not wire.is_feedback:
                in_degree[wire.target.id] += 1

        queue = deque(
            c for c in self.graph.cells if in_degree[c.id] == 0
        )

        while queue:
            cell = queue.popleft()

            # Infer output wire types from this cell
            for wire in cell.outputs:
                wire.wire_type = self._infer_wire_type(wire)

            # Validate inputs match cell expectations
            self._validate_cell_inputs(cell)

            # Decrement downstream in-degrees
            for wire in cell.outputs:
                nxt = wire.target
                in_degree[nxt.id] -= 1
                if in_degree[nxt.id] == 0:
                    queue.append(nxt)

    def _validate_cell_inputs(self, cell: Cell):
        if not cell.inputs:
            return

        if cell.kind == "COLLECT":
            self._expect_input_types(cell, ("value", "stream"), "{collect}", "value/stream")

        elif cell.kind == "REDUCE":
            self._expect_input_types(cell, ("bag",), f"({cell.label})", "bag")

        elif cell.kind == "GATE":
            # Gate needs at least one signal input
            signal_inputs = [w for w in cell.inputs if w.wire_type == "signal"]
            if not signal_inputs:
                raise GridFlowTypeError(
                    f"Line {cell.row}: ? gate needs at least one signal input, "
                    f"got {[w.wire_type for w in cell.inputs]}"
                )

        elif cell.kind == "TRANSFORM":
            raw_label = cell.label
            label = raw_label.lower()
            if label.startswith("map:"):
                self._expect_input_types(cell, ("stream",), f"[{cell.label}]", "stream")
                plate_name = raw_label[len("map:"):].strip()
                if plate_name not in self.graph.plates:
                    raise GridFlowTypeError(
                        f"Line {cell.row}: [{cell.label}] references "
                        f"unknown plate '{plate_name}'"
                    )
                return
            if label.startswith("const:"):
                self._expect_input_types(cell, ("value",), f"[{cell.label}]", "value")
                return

            rule = self._TRANSFORM_IO.get(label)
            if rule:
                expected_in, _ = rule
                self._expect_input_types(
                    cell,
                    (expected_in,),
                    f"[{cell.label}]",
                    expected_in,
                )

    @staticmethod
    def _expect_input_types(
        cell: Cell,
        allowed_types: Tuple[str, ...],
        cell_name: str,
        expected_text: str,
    ):
        for wire in cell.inputs:
            if wire.wire_type not in allowed_types:
                raise GridFlowTypeError(
                    f"Line {cell.row}: {cell_name} expects '{expected_text}', "
                    f"got '{wire.wire_type}' from '{wire.source.label}'"
                )
