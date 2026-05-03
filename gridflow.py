"""
GridFlow CLI
Usage:  python gridflow.py run <file.gf> [key=value ...]
        python gridflow.py check <file.gf>
        python gridflow.py demo
"""

import sys
from lexer import lex
from parser import Parser, GridFlowTypeError, GridFlowParseError
from interpreter import Interpreter, GridFlowRuntimeError


# ── Runner ─────────────────────────────────────────────────────────────────────

def run_file(path: str, inputs: dict, verbose: bool = False):
    with open(path) as f:
        source = f.read()
    run_source(source, inputs, verbose=verbose, label=path)


def run_source(source: str, inputs: dict, verbose: bool = False, label: str = "<source>"):
    print(f"\n{'─'*50}")
    print(f"  GridFlow — {label}")
    print(f"{'─'*50}")

    # Lex
    tokens = lex(source)
    if verbose:
        print(f"  Lexer produced {len(tokens)} tokens")

    # Parse
    parser = Parser(tokens)
    try:
        graph = parser.parse()
    except (GridFlowTypeError, GridFlowParseError) as e:
        print(f"  ERROR: {e}")
        return

    print(f"  Graph: {len(graph.cells)} cells, {len(graph.wires)} wires")
    print(f"  Inputs:  {[c.port_name for c in graph.input_ports]}")
    print(f"  Outputs: {[c.port_name for c in graph.output_ports]}")

    # Run
    interp = Interpreter(graph)
    try:
        outputs = interp.run(inputs, verbose=verbose)
    except GridFlowRuntimeError as e:
        print(f"  RUNTIME ERROR: {e}")
        return

    print(f"\n  Results:")
    for k, v in outputs.items():
        print(f"    {k} = {v!r}")
    print()


# ── Sample programs ────────────────────────────────────────────────────────────

SAMPLE_1 = """
name:value >──[trim]──[upper]──< result:value
"""

SAMPLE_2 = """
score:value >──[≥60]──< grade:value
"""

SAMPLE_3 = """
a:value >──────────────┐
                        {collect}──(avg)──< average:value
b:value >──────────────┘
"""

SAMPLE_4_PIPELINE = """
plate shout:
    text:value >──[trim]──[upper]──[!]──< out:value
end

message:value >──[shout]──< result:value
"""

# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_kv_args(args):
    inputs = {}
    for arg in args:
        if "=" in arg:
            k, v = arg.split("=", 1)
            # Try to coerce to number
            try:    inputs[k] = int(v)
            except ValueError:
                try: inputs[k] = float(v)
                except ValueError:
                    inputs[k] = v
    return inputs


def cmd_demo():
    print("\n" + "="*50)
    print("  GridFlow — Demo Programs")
    print("="*50)

    run_source(
        SAMPLE_1,
        {"name": "  hello world  "},
        label="Sample 1: string pipeline"
    )

    run_source(
        SAMPLE_2,
        {"score": 75},
        label="Sample 2: gate / branch"
    )

    run_source(
        SAMPLE_3,
        {"a": 40, "b": 60},
        label="Sample 3: merge and reduce (average)"
    )


def cmd_run(args):
    if not args:
        print("Usage: python gridflow.py run <file.gf> [key=value ...]")
        sys.exit(1)
    path   = args[0]
    inputs = parse_kv_args(args[1:])
    run_file(path, inputs, verbose="--verbose" in args)


def cmd_check(args):
    if not args:
        print("Usage: python gridflow.py check <file.gf>")
        sys.exit(1)
    path = args[0]
    with open(path) as f:
        source = f.read()
    tokens = lex(source)
    parser = Parser(tokens)
    try:
        graph = parser.parse()
        print(f"OK — {len(graph.cells)} cells, {len(graph.wires)} wires, "
              f"{len(graph.plates)} plates")
    except (GridFlowTypeError, GridFlowParseError) as e:
        print(f"TYPE ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "demo":
        cmd_demo()
    elif args[0] == "run":
        cmd_run(args[1:])
    elif args[0] == "check":
        cmd_check(args[1:])
    else:
        print("Commands: run, check, demo")
        sys.exit(1)
