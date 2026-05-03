# GridFlo

GridFlo is a small programming language interpreter written in Python. GridFlo
programs are drawn as two-dimensional dataflow grids in `.gf` files, then parsed
and executed as graphs.

Instead of writing code as nested statements, you connect cells with wires:

```gf
name:value >──[trim]──[upper]──< result:value
```

Data enters through input ports, moves along wires, passes through transform
cells, and exits through output ports.

## Project Status

GridFlo is an experimental interpreter and language prototype. It is useful for
trying visual dataflow ideas, writing small examples, and exploring how a 2D
programming language could work.

It currently has:

- A lexer for scanning `.gf` grid files.
- A parser that builds a typed cell graph.
- A pull-based interpreter for running the graph.
- Built-in transforms for strings, numbers, comparisons, streams, maps, gates,
  collection, and reduction.
- Reusable `plate` blocks, which are sub-graphs that can be called by name.

There are no third-party dependencies. Everything runs with the Python standard
library.

## Requirements

- Python 3.9 or newer is recommended.
- No package installation is required.

Check your Python version:

```bash
python --version
```

## Repository Layout

```text
GridFlo/
├── gridflow.py       # CLI entry point
├── lexer.py          # Turns source text into positioned tokens
├── parser.py         # Builds and type-checks the cell graph
├── interpreter.py    # Executes the cell graph
├── sample programs/  # Runnable GridFlo example programs
│   ├── hello.gf      # Simple example program
│   ├── grade.gf      # Simple comparison example
│   ├── average.gf    # Collect and reduce example
│   ├── shout.gf      # Plate/sub-graph example
│   └── fizzbuzz.gf   # Official FizzBuzz example
└── landing page/     # Static website for the GridFlo project
    ├── index.html    # Landing page
    ├── docs.html     # README-style documentation page
    ├── styles.css    # Shared page styling
    └── script.js     # Landing page sample switcher
```

## Quick Start

Run the hello example:

```bash
python gridflow.py run "sample programs/hello.gf"
```

Expected result:

```text
output = 'GRIDFLO'
```

Run FizzBuzz:

```bash
python gridflow.py run "sample programs/fizzbuzz.gf" n=15
```

Expected result:

```python
answer = ['1', '2', 'Fizz', '4', 'Buzz', 'Fizz', '7', '8', 'Fizz', 'Buzz', '11', 'Fizz', '13', '14', 'FizzBuzz']
```

Type-check a program without running it:

```bash
python gridflow.py check "sample programs/fizzbuzz.gf"
```

Run the built-in demos:

```bash
python gridflow.py demo
```

Run with verbose execution output:

```bash
python gridflow.py run "sample programs/fizzbuzz.gf" n=15 --verbose
```

## Landing Page

The `landing page/` folder contains a small static website for GridFlo. It has a
home page, a styled documentation page based on this README, and interactive
sample tabs.

Open it directly:

```bash
open "landing page/index.html"
```

Or serve it locally from the repository root:

```bash
python -m http.server 8000
```

Then visit:

```text
http://localhost:8000/landing%20page/
```

## Saved Example Programs

The repository includes five runnable `.gf` example programs:

When running one of these from the repository root, include the `sample programs/`
folder in the path, for example `python gridflow.py run "sample programs/fizzbuzz.gf" n=20`.

| File | Purpose | Example command |
|---|---|---|
| `sample programs/hello.gf` | Simple string pipeline and two-input concatenation | `python gridflow.py run "sample programs/hello.gf"` |
| `sample programs/grade.gf` | Simple comparison program | `python gridflow.py run "sample programs/grade.gf" score=75` |
| `sample programs/average.gf` | Collects two inputs and reduces them with `(avg)` | `python gridflow.py run "sample programs/average.gf" a=40 b=60` |
| `sample programs/shout.gf` | Uses a reusable `plate` to trim, uppercase, and add `!` | `python gridflow.py run "sample programs/shout.gf" message=" hello "` |
| `sample programs/fizzbuzz.gf` | Complex stream/map FizzBuzz program | `python gridflow.py run "sample programs/fizzbuzz.gf" n=15` |

## Command Reference

### Run A Program

```bash
python gridflow.py run <file.gf> [key=value ...]
```

Examples:

```bash
python gridflow.py run "sample programs/hello.gf"
python gridflow.py run "sample programs/grade.gf" score=75
python gridflow.py run "sample programs/average.gf" a=40 b=60
python gridflow.py run "sample programs/shout.gf" message=" hello "
python gridflow.py run "sample programs/fizzbuzz.gf" n=15
python gridflow.py run my_program.gf name=Mateo score=75
```

Input values are passed as `key=value` pairs. The CLI tries to convert numeric
inputs to `int` or `float`. If conversion fails, the value is passed as a string.

### Check A Program

```bash
python gridflow.py check <file.gf>
```

This lexes, parses, wires, and type-checks the program without executing it.

### Run Demos

```bash
python gridflow.py demo
```

This runs the sample programs embedded in `gridflow.py`.

Run syntax checks for the Python files:

```bash
python -m py_compile gridflow.py lexer.py parser.py interpreter.py
```

## Core Idea

GridFlo programs are made of cells connected by wires.

```gf
input:value >──[transform]──< output:value
```

The flow is:

```text
input port -> transform cell -> output port
```

Each cell has a position in the 2D source grid. The parser uses those positions
to trace wire characters and build a directed graph.

## Supported Types

GridFlo currently supports four wire types:

- `value`: A single value, such as a number, string, or boolean.
- `stream`: A sequence/list of values, such as `[1, 2, 3]`.
- `signal`: A boolean condition, usually produced by transforms like `[?=0]`.
- `bag`: A collected group of values, usually created by `{collect}` and
  consumed by reducers like `(sum)` or `(avg)`.

Example port declarations:

```gf
name:value >
items:stream >
flag:signal >
values:bag >
```

Older versions used the name `scalar`. That type has been renamed to `value`.
New `.gf` files should use `value`.

## Language Reference

### Input Ports

Input ports receive values from the command line.

```gf
name:value >
```

Run with:

```bash
python gridflow.py run program.gf name="  hello  "
```

### Output Ports

Output ports expose final values.

```gf
< result:value
```

The CLI prints output ports by name.

### Constants

Constants inject literal values into the graph.

```gf
*42
*"hello world"
*true
*false
```

Unquoted constants are parsed as numbers when possible. Quoted constants are
treated as strings.

### Wires

Wires connect cells.

Horizontal wires:

```gf
──
--
```

Vertical wires:

```gf
│
|
```

Corners:

```gf
┐ ┘ └ ┌
```

Junctions:

```gf
┤ ├ ┬ ┴ ┼ +
```

Taps:

```gf
·
.
```

Use monospace editing and keep alignment exact. GridFlo relies on character
positions to trace connections.

## Transform Cells

Transform cells are written in square brackets:

```gf
[upper]
```

They take input from incoming wires and push results to outgoing wires.

### String Transforms

```gf
[trim]     # remove leading/trailing whitespace
[upper]    # uppercase
[lower]    # lowercase
[str]      # convert to string
[len]      # string length
[reverse]  # reverse string representation
[split]    # split string into a stream/list of words
[!]        # append "!" to the string representation
```

Example:

```gf
name:value >──[trim]──[upper]──[!]──< result:value
```

### Numeric Conversion

```gf
[int]
[float]
```

### Arithmetic With Literals

```gf
[+1]
[-5]
[×2]
[*2]
[÷3]
[/3]
[%2]
[^2]
```

Example:

```gf
n:value >──[×2]──< doubled:value
```

### Two-Input Arithmetic

Some transform labels can also work with two inputs:

```gf
[+]
[-]
[×]
[*]
[÷]
[/]
[%]
[^]
```

Example from `hello.gf`:

```gf
*"grid"──[upper]──┐
                  [+]──[trim]──< output:value
*"flo"──[upper]──┘
```

This produces:

```python
'GRIDFLO'
```

### Comparisons

Comparison transforms return boolean values.

```gf
[=5]
[==5]
[!=0]
[≠0]
[>3]
[<10]
[>=60]
[≤100]
```

### Signal-Producing Comparisons

Labels starting with `?` produce `signal` values. These are designed to feed
the `?` gate cell.

```gf
[?=0]
[?!=0]
[?>5]
[?<10]
[?>=60]
[?<=100]
```

Example:

```gf
n:value >──[%3]──[?=0]──?──[const:Fizz]──< out:value
```

## Gates

The `?` cell routes based on a signal input.

- If the signal is true, the value goes to the right branch.
- If the signal is false, the value goes down.

Example:

```gf
n:value >──[%3]──[?=0]──?──[const:Fizz]──< out:value
                         │
                         [str]───────────< out:value
```

This means:

- If `n % 3 == 0`, output `"Fizz"`.
- Otherwise, output `n` as a string.

For signal comparisons like `[?=0]`, GridFlo remembers the original value being
tested. That lets a graph compute `n % 3` while still routing the original `n`
through the gate branch.

## Streams

Streams are list-like values.

### `[range]`

`[range]` turns an integer `n` into a stream from `1` through `n`.

```gf
n:value >──[range]──< out:stream
```

For `n=4`, the output is:

```python
[1, 2, 3, 4]
```

### `[map:<plate>]`

`[map:<plate>]` runs a named plate once for each item in a stream.

```gf
plate double:
i:value >──[×2]──< out:value
end

n:value >──[range]──[map:double]──< out:stream
```

For `n=4`, the output is:

```python
[2, 4, 6, 8]
```

The parser validates that the plate named by `[map:<plate>]` exists.

### `[const:<text>]`

`[const:<text>]` replaces the incoming value with fixed text.

```gf
n:value >──[const:Fizz]──< out:value
```

For any input, the output is:

```python
'Fizz'
```

This is useful in branches where a condition decides which string to return.

## Collect And Reduce

`{collect}` gathers multiple incoming values into a `bag`.

```gf
a:value >──────────────┐
                        {collect}──(avg)──< average:value
b:value >──────────────┘
```

Reducers collapse a bag into one value.

Supported reducers include:

```gf
(sum)
(+)
(max)
(min)
(count)
(#)
(avg)
(mean)
(join)
(,)
(product)
(×)
```

## Plates

Plates are reusable sub-graphs.

```gf
plate shout:
text:value >──[trim]──[upper]──[!]──< out:value
end

message:value >──[shout]──< result:value
```

The `plate shout:` block defines a reusable graph named `shout`. The main graph
calls it with `[shout]`.

Plates are also used by `[map:<plate>]` to process each item in a stream.

## FizzBuzz Example

`fizzbuzz.gf` implements the official FizzBuzz problem:

```gf
plate fizzbuzzItem:
i:value >──[%15]──[?=0]──?──[const:FizzBuzz]──< out:value
                         │
                         [%3]──[?=0]──?──[const:Fizz]──< out:value
                                       │
                                       [%5]──[?=0]──?──[const:Buzz]──< out:value
                                                     │
                                                     [str]──< out:value
end

n:value >──[range]──[map:fizzbuzzItem]──< answer:stream
```

How it works:

1. `n:value >` receives the input number.
2. `[range]` creates `[1, 2, ..., n]`.
3. `[map:fizzbuzzItem]` runs `fizzbuzzItem` once per number.
4. `fizzbuzzItem` checks divisibility by `15`, then `3`, then `5`.
5. The first matching branch returns `"FizzBuzz"`, `"Fizz"`, or `"Buzz"`.
6. If no branch matches, `[str]` returns the number as a string.
7. `< answer:stream` outputs the full list.

Run it:

```bash
python gridflow.py run "sample programs/fizzbuzz.gf" n=15
```

## Architecture

GridFlo has three main phases:

```text
source text -> lexer -> parser -> interpreter
```

### Lexer

`lexer.py` scans the source file character by character.

It produces tokens with:

- Token type
- Label
- Row position
- Column position
- Port name and port type when applicable

Wire characters are tokenized too. They are not executable cells, but the parser
uses them to discover connections.

### Parser

`parser.py` turns tokens into a `CellGraph`.

Main parser steps:

1. Split `plate name:` / `end` blocks into sub-graphs.
2. Create `Cell` objects for ports, transforms, gates, constants, reducers, and
   other executable cells.
3. Build a spatial index by `(row, col)`.
4. Trace wires rightward and downward from cells.
5. Create `Wire` objects between source and target cells.
6. Infer and validate wire types.

Type errors raise `GridFlowTypeError`.

### Interpreter

`interpreter.py` executes a `CellGraph`.

Execution is pull-based:

1. Input ports and constants seed their outgoing wires.
2. Cells become ready when their input wires have values.
3. Ready cells fire and push results to outgoing wires.
4. Output ports collect final results.

The interpreter also supports:

- Gate routing by branch direction.
- Plate calls.
- Mapping plates over streams.
- Internal value tracking so predicates can test transformed values while gates
  still route the original value.

## Development Workflow

Recommended checks before committing changes:

```bash
python gridflow.py run "sample programs/hello.gf"
python gridflow.py run "sample programs/grade.gf" score=75
python gridflow.py run "sample programs/average.gf" a=40 b=60
python gridflow.py run "sample programs/shout.gf" message=" hello "
python gridflow.py check "sample programs/fizzbuzz.gf"
python gridflow.py run "sample programs/fizzbuzz.gf" n=15
python gridflow.py demo
python -m py_compile gridflow.py lexer.py parser.py interpreter.py
```

If you change the language syntax, update:

- `lexer.py` if new source tokens are needed.
- `parser.py` if new cells, types, or wire rules are needed.
- `interpreter.py` if runtime behavior changes.
- `CHANGES.md` with a short human-readable summary.
- `README.md` so users know how to use the feature.

## Troubleshooting

### `Inputs: []` When You Expected An Input

Make sure the input port has a `>` marker.

Correct:

```gf
n:value >
```

Incorrect:

```gf
n:value
```

### A Wire Does Not Connect

GridFlo is position-sensitive. Check that:

- Horizontal wires start at the cell's right edge.
- Vertical wires are aligned under the source cell or branch point.
- Corners line up exactly with the path.
- You are editing in a monospace font.

Use verbose mode to see more runtime detail:

```bash
python gridflow.py run file.gf --verbose
```

### A Gate Does Not Take The Expected Branch

Make sure the gate receives a `signal`.

Signal-producing transforms start with `?`, for example:

```gf
[?=0]
[?>5]
[?<=10]
```

Plain comparisons like `[=0]` return boolean values, but the `?` gate is designed
to work with `signal` inputs.

### `[map:<plate>]` Fails During Check

Make sure the plate exists and the spelling matches exactly.

Correct:

```gf
plate item:
i:value >──[str]──< out:value
end

n:value >──[range]──[map:item]──< answer:stream
```

Incorrect:

```gf
n:value >──[range]──[map:missing]──< answer:stream
```

### `scalar` Type Errors

Use `value` instead of `scalar`.

Correct:

```gf
name:value >
```

Incorrect:

```gf
name:scalar >
```

## Current Limitations

- The language is experimental and intentionally small.
- Wire tracing depends on exact character positions.
- There is no package manager or module system.
- The CLI prints Python-style representations of output values.
- Error messages are basic and may point to graph rows rather than full source
  spans.
- Feedback and latch behavior exists in the interpreter, but complex feedback
  programs need careful testing.

## License

No license file is currently included in this repository.
