"""
GridFlow Interpreter
Executes a CellGraph using pull-based dataflow semantics.
Cells fire when all their inputs are satisfied.
Latch cells anchor feedback loops across ticks.
"""

from __future__ import annotations
from dataclasses import dataclass
from collections import deque
from typing import Any, Dict, List, Optional, Set
from parser import CellGraph, Cell, Wire
import math
import operator


# Sentinel — a wire with no value yet
_EMPTY = object()


@dataclass(frozen=True)
class _Signal:
    """Boolean branch result plus the value that was tested."""
    matched: bool
    value: Any


@dataclass(frozen=True)
class _TrackedValue:
    """Current transformed value plus the original value to route through gates."""
    current: Any
    original: Any


class GridFlowRuntimeError(Exception):
    pass


def _current_value(value: Any) -> Any:
    return value.current if isinstance(value, _TrackedValue) else value


def _original_value(value: Any) -> Any:
    return value.original if isinstance(value, _TrackedValue) else value


def _public_value(value: Any) -> Any:
    if isinstance(value, _TrackedValue):
        return value.current
    if isinstance(value, _Signal):
        return value.matched
    return value


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    return [value]


# ── Built-in cell implementations ─────────────────────────────────────────────

def _apply_transform(label: str, value: Any) -> Any:
    """Apply a single-input transform cell to a value."""
    label = label.strip()
    current = _current_value(value)

    # String ops
    if label == "trim":    return str(current).strip()
    if label == "upper":   return str(current).upper()
    if label == "lower":   return str(current).lower()
    if label == "str":     return str(current)
    if label == "int":     return int(float(str(current)))
    if label == "float":   return float(str(current))
    if label == "len":     return len(str(current))
    if label == "reverse": return str(current)[::-1]
    if label == "split":   return str(current).split()
    if label == "range":
        limit = int(float(str(current)))
        if limit < 0:
            raise GridFlowRuntimeError("[range] expects a non-negative integer")
        return list(range(1, limit + 1))
    if label.startswith("const:"):
        return label[len("const:"):]

    # Boolean ops (single input)
    if label == "not":     return not current
    if label == "!":       return str(current) + "!"

    # Signal-producing comparisons: ?=0, ?!=0, ?>5, ?<10 etc.
    # These output a boolean (signal) instead of value
    if label.startswith("?"):
        cmp = label[1:]  # strip the ?
        for op_sym, op_fn in [
            (">=", operator.ge), ("<=", operator.le),
            ("!=", operator.ne), ("==", operator.eq),
            ("=",  operator.eq),
            (">",  operator.gt), ("<",  operator.lt),
        ]:
            if cmp.startswith(op_sym):
                try:
                    operand = float(cmp[len(op_sym):])
                    return _Signal(
                        op_fn(float(_current_value(value)), operand),
                        _original_value(value),
                    )
                except ValueError as e:
                    raise GridFlowRuntimeError(
                        f"Signal comparison [{label}] failed on {value!r}: {e}"
                    )
        raise GridFlowRuntimeError(f"Unknown signal comparison: [{label}]")

    # Arithmetic with literal: [+1], [×2], [÷3], [-5], [%2], [^2]
    for op_sym, op_fn in [
        ("+", operator.add),
        ("-", operator.sub),
        ("×", operator.mul), ("*", operator.mul),
        ("÷", operator.truediv), ("/", operator.truediv),
        ("%", operator.mod),
        ("^", operator.pow),
    ]:
        if label.startswith(op_sym):
            try:
                operand = float(label[len(op_sym):])
                result  = op_fn(float(_current_value(value)), operand)
                # Return int if whole number
                result = int(result) if result == int(result) else result
                return _TrackedValue(result, _original_value(value))
            except (ValueError, ZeroDivisionError) as e:
                raise GridFlowRuntimeError(
                    f"Transform [{label}] failed on value {value!r}: {e}"
                )

    # Comparison with literal: [=5], [≠0], [>3], [<10], [≥0], [≤100]
    for op_sym, op_fn in [
        ("≥", operator.ge), (">=", operator.ge),
        ("≤", operator.le), ("<=", operator.le),
        ("≠", operator.ne), ("!=", operator.ne),
        ("=", operator.eq),  ("==", operator.eq),
        (">", operator.gt),
        ("<", operator.lt),
    ]:
        if label.startswith(op_sym):
            try:
                operand = float(label[len(op_sym):])
                return op_fn(float(_current_value(value)), operand)
            except ValueError as e:
                raise GridFlowRuntimeError(
                    f"Comparison [{label}] failed on value {value!r}: {e}"
                )

    raise GridFlowRuntimeError(f"Unknown transform cell: [{label}]")


def _apply_two_input_transform(label: str, a: Any, b: Any) -> Any:
    """Apply a two-input math cell: [+] [-] [×] [÷] [%] [=] [>] etc."""
    label = label.strip()
    ops = {
        "+": operator.add,   "-":  operator.sub,
        "×": operator.mul,   "*":  operator.mul,
        "÷": operator.truediv, "/": operator.truediv,
        "%": operator.mod,   "^":  operator.pow,
        "=": operator.eq,    "==": operator.eq,
        "≠": operator.ne,    "!=": operator.ne,
        ">": operator.gt,    "<":  operator.lt,
        "≥": operator.ge,    "≤":  operator.le,
        "and": lambda x, y: x and y,
        "or":  lambda x, y: x or y,
    }
    fn = ops.get(label)
    if fn is None:
        raise GridFlowRuntimeError(f"Unknown two-input cell: [{label}]")
    try:
        a = _current_value(a)
        b = _current_value(b)
        return fn(float(a) if isinstance(a, (int, float)) else a,
                  float(b) if isinstance(b, (int, float)) else b)
    except ZeroDivisionError:
        raise GridFlowRuntimeError(f"Division by zero in [{label}]")


def _apply_reduce(label: str, bag: list) -> Any:
    """Collapse a bag using a named reduction."""
    label = label.strip().lower()
    if not bag:
        raise GridFlowRuntimeError(f"({label}) received empty bag")
    public_bag = [_public_value(x) for x in bag]
    numeric = [float(_current_value(x)) for x in bag]
    if label in ("sum", "+"):      return sum(numeric)
    if label in ("max",):          return max(numeric)
    if label in ("min",):          return min(numeric)
    if label in ("count", "#"):    return len(bag)
    if label in ("avg", "mean"):   return sum(numeric) / len(numeric)
    if label in ("join", ","):     return ", ".join(str(x) for x in public_bag)
    if label in ("product", "×"):  return math.prod(numeric)
    raise GridFlowRuntimeError(f"Unknown reducer: ({label})")


# ── Interpreter ────────────────────────────────────────────────────────────────

class Interpreter:
    def __init__(self, graph: CellGraph, max_ticks: int = 1000):
        self.graph     = graph
        self.max_ticks = max_ticks

        # wire_id → value  (wire_id = id(wire))
        self._wire_values: Dict[int, Any] = {}
        # latch_cell_id → stored value
        self._latches: Dict[str, Any] = {}
        # Cells that have already fired in this single-shot graph run
        self._fired_cells: Set[str] = set()

    def run(self, inputs: Dict[str, Any], verbose: bool = False) -> Dict[str, Any]:
        """
        Execute the graph.
        inputs  : {"port_name": value, ...}
        returns : {"port_name": value, ...}
        """
        self._wire_values = {}
        self._latches     = {}
        self._fired_cells = set()

        # ── Seed input ports ──────────────────────────────────────────────
        for cell in self.graph.input_ports:
            name = cell.port_name
            if name not in inputs:
                raise GridFlowRuntimeError(
                    f"Missing input for port '{name}'"
                )
            val = inputs[name]
            # Push value onto all output wires of this port
            for wire in cell.outputs:
                self._set_wire(wire, val)

        # ── Seed constants ────────────────────────────────────────────────
        for cell in self.graph.cells:
            if cell.kind == "CONSTANT":
                val = self._parse_literal(cell.label)
                for wire in cell.outputs:
                    self._set_wire(wire, val)

        # ── Main execution loop ───────────────────────────────────────────
        outputs: Dict[str, Any] = {}

        for tick in range(self.max_ticks):
            if verbose:
                print(f"  tick {tick}: {len(self._ready_cells())} cells ready")

            ready = self._ready_cells()
            if not ready:
                break

            for cell in ready:
                if cell.kind == "GATE":
                    self._fire_gate(cell)
                    self._fired_cells.add(cell.id)
                    continue

                result = self._fire(cell)

                if result is _EMPTY:
                    continue

                # Push result onto output wires
                if cell.kind == "OUTPUT_PORT":
                    outputs[cell.port_name] = result
                else:
                    for wire in cell.outputs:
                        if not wire.is_feedback:
                            self._set_wire(wire, result)
                        else:
                            # Feedback wire — store in latch for next tick
                            # Find the latch cell on this feedback path
                            self._latches[wire.target.id] = result

                if not cell.is_latch:
                    self._fired_cells.add(cell.id)

            # ── Tick latch values forward ─────────────────────────────────
            for cell in self.graph.cells:
                if cell.is_latch and cell.id in self._latches:
                    val = self._latches.pop(cell.id)
                    for wire in cell.outputs:
                        self._set_wire(wire, val)

        return outputs

    # ── Readiness check ────────────────────────────────────────────────────

    def _ready_cells(self) -> List[Cell]:
        """Return all cells whose input wires are all satisfied."""
        ready = []
        for cell in self.graph.cells:
            if cell.kind in ("INPUT_PORT", "CONSTANT"):
                continue
            if cell.id in self._fired_cells and not cell.is_latch:
                continue
            if cell.kind == "OUTPUT_PORT":
                if cell.inputs and all(
                    self._wire_values.get(id(w), _EMPTY) is not _EMPTY
                    for w in cell.inputs
                ):
                    ready.append(cell)
                continue
            # Skip already-fired cells (all outputs satisfied)
            if cell.outputs and all(
                self._wire_values.get(id(w), _EMPTY) is not _EMPTY
                for w in cell.outputs
            ):
                continue
            # Feedback/latch inputs are satisfied by the latch mechanism
            effective_inputs = [w for w in cell.inputs if not w.is_feedback]
            if effective_inputs and all(
                self._wire_values.get(id(w), _EMPTY) is not _EMPTY
                for w in effective_inputs
            ):
                ready.append(cell)
            elif not effective_inputs and cell.is_latch:
                # Latch with no non-feedback input is seeded externally
                if cell.id in self._latches:
                    ready.append(cell)
        return ready

    # ── Cell firing ────────────────────────────────────────────────────────

    def _fire(self, cell: Cell) -> Any:
        """Execute a single cell and return its output value."""

        if cell.kind == "OUTPUT_PORT":
            if not cell.inputs:
                return _EMPTY
            return _public_value(self._get_wire(cell.inputs[0]))

        if cell.kind == "LATCH":
            # Latch emits its stored value
            return self._latches.get(cell.id, _EMPTY)

        if cell.kind == "INVERT":
            val = self._get_wire(cell.inputs[0]) if cell.inputs else False
            return not _current_value(val)

        if cell.kind == "COUNTER":
            # Count how many values have passed — track in latch storage
            count = self._latches.get(f"counter_{cell.id}", 0) + 1
            self._latches[f"counter_{cell.id}"] = count
            return count

        if cell.kind == "DELAY":
            # Buffer: store current value, emit previous
            val     = self._get_wire(cell.inputs[0]) if cell.inputs else None
            prev    = self._latches.get(f"delay_{cell.id}", None)
            self._latches[f"delay_{cell.id}"] = _public_value(val)
            return prev

        if cell.kind == "COLLECT":
            # Gather all input values into a list (bag)
            return [_public_value(self._get_wire(w)) for w in cell.inputs
                    if self._wire_values.get(id(w), _EMPTY) is not _EMPTY]

        if cell.kind == "REDUCE":
            bag = self._get_wire(cell.inputs[0]) if cell.inputs else []
            if not isinstance(bag, list):
                bag = [bag]
            return _apply_reduce(cell.label, bag)

        if cell.kind == "TRANSFORM":
            label = cell.label.strip()

            # Plate call — look up the plate sub-graph and run it
            if label in self.graph.plates:
                plate_graph  = self.graph.plates[label]
                plate_interp = Interpreter(plate_graph, self.max_ticks)
                plate_inputs = {}
                for i, inp_cell in enumerate(plate_graph.input_ports):
                    if i < len(cell.inputs):
                        plate_inputs[inp_cell.port_name] = self._get_wire(cell.inputs[i])
                result = plate_interp.run(plate_inputs)
                if plate_graph.output_ports:
                    first_out = plate_graph.output_ports[0].port_name
                    return result.get(first_out)

            if label.startswith("map:"):
                plate_name = label[len("map:"):].strip()
                if plate_name not in self.graph.plates:
                    raise GridFlowRuntimeError(f"Unknown plate for map: [{plate_name}]")
                if not cell.inputs:
                    return []

                plate_graph = self.graph.plates[plate_name]
                if not plate_graph.input_ports:
                    raise GridFlowRuntimeError(
                        f"Plate '{plate_name}' used by map has no input port"
                    )
                if not plate_graph.output_ports:
                    raise GridFlowRuntimeError(
                        f"Plate '{plate_name}' used by map has no output port"
                    )

                stream = _as_list(_public_value(self._get_wire(cell.inputs[0])))
                input_name = plate_graph.input_ports[0].port_name
                output_name = plate_graph.output_ports[0].port_name
                results = []
                for item in stream:
                    plate_interp = Interpreter(plate_graph, self.max_ticks)
                    plate_outputs = plate_interp.run({input_name: item})
                    results.append(plate_outputs.get(output_name))
                return results

            # Two-input arithmetic/logic cells: [+] [-] [×] etc.
            if label in ("+", "-", "×", "*", "÷", "/", "%", "^",
                         "=", "==", "≠", "!=", ">", "<", "≥", "≤",
                         "and", "or"):
                if len(cell.inputs) >= 2:
                    a = self._get_wire(cell.inputs[0])
                    b = self._get_wire(cell.inputs[1])
                    return _apply_two_input_transform(label, a, b)
                elif len(cell.inputs) == 1:
                    # Single input — treat as identity
                    return self._get_wire(cell.inputs[0])

            # Single-input transform
            val = self._get_wire(cell.inputs[0]) if cell.inputs else None
            return _apply_transform(label, val)

        return _EMPTY

    def _fire_gate(self, cell: Cell) -> bool:
        """Route a gate's value to the right branch when true, down when false."""
        signal_val = None
        pass_val = None

        for wire in cell.inputs:
            value = self._get_wire(wire)
            if wire.wire_type == "signal":
                signal_val = value
            else:
                pass_val = value

        if signal_val is None and cell.inputs:
            signal_val = self._get_wire(cell.inputs[0])

        if isinstance(signal_val, _Signal):
            matched = signal_val.matched
            if pass_val is None:
                pass_val = signal_val.value
        else:
            matched = bool(signal_val)
            if pass_val is None:
                pass_val = signal_val

        branch = "right" if matched else "down"
        fired = False
        for wire in cell.outputs:
            if wire.direction == branch:
                self._set_wire(wire, pass_val)
                fired = True
        return fired

    # ── Wire helpers ───────────────────────────────────────────────────────

    def _set_wire(self, wire: Wire, value: Any):
        self._wire_values[id(wire)] = value

    def _get_wire(self, wire: Wire) -> Any:
        val = self._wire_values.get(id(wire), _EMPTY)
        if val is _EMPTY:
            raise GridFlowRuntimeError(
                f"Wire from '{wire.source.label}' has no value yet"
            )
        return val

    @staticmethod
    def _parse_literal(label: str) -> Any:
        """Parse a constant cell label into a Python value."""
        try:
            return int(label)
        except ValueError:
            pass
        try:
            return float(label)
        except ValueError:
            pass
        if label.lower() == "true":  return True
        if label.lower() == "false": return False
        return label  # string
