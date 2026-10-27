# pysurface

pysurface reads a Python package and writes a compact outline of its API surface: every module, class, field, method, function and constant, with its signature, its docstring and the comments written beside it, and no function bodies. You see the shape of a whole package in one file that you can skim, search, or hand to a reviewer or a language model.

It reads the source with Python's own parser and never imports or runs the package. It needs no dependencies, no network and no installed package, so it works on a fresh clone and on code that does not run right now. It is fast: about 0.2 seconds for a 70-module package. On tomd, 750 KB of Python source becomes a 150 KB report, or 95 KB with `--brief`.

## Why

Opening a codebase file by file is slow for a person and expensive for a language model, which spends a tool call and a slice of context on every file it reads. One pysurface report gives either reader the declarations, docstrings and comments of the whole package at once, at a fraction of the size of the source. The report is plain text produced by a deterministic program, not by a model, so it is fast, repeatable and cannot invent anything.

## What it does

- **Two files from one model.** `<name>.api.md` and `<name>.api.html`. Both come from the same parse, so their text always agrees.
- **A self-contained, linked HTML file.** Inline CSS, no JavaScript, no network requests. A sticky sidebar lists every module, class and function. Every declaration has an anchor, and a type name that matches a class in the report links to it. Colors follow your system's light or dark setting.
- **A compact Markdown file** with a contents list, one section per module, and an index of every name at the end.
- **Comments kept.** Docstrings, the comment block directly above a declaration, and the comment at the end of a field's line all stay with the item they belong to.
- **What calls what.** Under each function and method, `# calls:` lists the package's own functions, methods and classes it calls, and `# called by:` lists the ones that call it, including private helpers that are not listed themselves. In the HTML each name links to its declaration. `--no-calls` leaves these lines out.
- **Where types are missing.** Under each function and method, `# untyped:` names the parameters with no annotation, and `return` when the return type is missing. A method's `self` or `cls` and `__init__`'s return are not counted. Each module, and the report as a whole, opens with a line such as `Typed: 40 of 42 functions and methods (95%)`, counting private and unlisted ones too; the percentage rounds down, so 100% means all of them. `--no-type-marks` leaves these out.
- **Links back to the source.** Each module and declaration links to its file and line, such as `evidence.py:73`. `--no-source-links` leaves them out.
- **A declaration diff.** `--diff OLD NEW` compares two git refs and prints only the declarations that changed, as a unified diff per module.

## Install

pysurface needs Python 3.9 or later and nothing else.

```
pip install .
```

or run it from a checkout without installing:

```
PYTHONPATH=src python -m pysurface <path>
```

## Run

```
pysurface <package-dir-or-file.py> [-o <out-dir>] [--name NAME]
pysurface <repo> --ref <git-ref> [--root <dir>] [-o <out-dir>]
pysurface <repo> --diff <old-ref> <new-ref> [--root <dir>]
```

- `<package-dir-or-file.py>` is a directory, read recursively, or a single `.py` file.
- `--ref` reads the source at a git ref with `git show`, without checking it out. `--root` limits it to one directory of the repository.
- `--diff` prints the declaration changes between two refs on stdout, as Markdown with a `diff` block per changed module.
- `-o` (or `--out`) is the directory to write into. It defaults to the current directory and is created if it is missing.
- `--name` names the report. It defaults to the directory's name.
- `--private` keeps module-level names that start with `_`. Without it they are counted, not shown. A class's private members are always shown, after its public ones under a `# private` line.
- `--brief` keeps only the first paragraph of each docstring.
- `--no-source-links` leaves out the links back to files and lines. The output then depends only on the declarations, so reformatting code or reordering classes, functions, methods and constants leaves the files byte for byte the same. Fields keep their declared order on purpose (it is a dataclass's constructor order), so reordering fields does change the output.
- `--source-base URL` puts a prefix in front of every source link, for example `../../` when the report lives two folders below the repository root, or a `https://github.com/<owner>/<repo>/blob/<ref>/` URL. Without it, links are relative paths from the output folder to the source.
- `--no-calls` leaves out the `# calls:` and `# called by:` lines.
- `--no-type-marks` leaves out the `# untyped:` lines and the `Typed:` counts.
- `--exclude GLOB` leaves out matching paths, and may be repeated. Test files (`tests/`, `test_*.py`, `*_test.py`, `conftest.py`) are left out by default; `--include-tests` keeps them.

pysurface prints the path of each file it writes on stdout, and the module count and time on stderr. Existing files with the same names are overwritten.

## What the output looks like

Each module gets one block. Its docstring comes first, then classes sorted by name, then functions sorted by name, then constants (names in capitals, and `__all__`). Inside a class:

- the decorators that change meaning (`@dataclass`, `@property`, `@staticmethod`, `@classmethod`, `@abstractmethod` and similar) and the bases;
- the docstring;
- fields and class constants in the order they are declared, because a dataclass's field order is its constructor's argument order;
- instance attributes set as `self.x = ...` in `__init__` or `__post_init__`, in the order they are first assigned, so ordinary classes show their state too;
- methods sorted by name, public ones first, then the private ones under `# private`;
- nested classes.

Definitions inside module-level `if` and `try` blocks (`if TYPE_CHECKING:`, version shims, `except ImportError:` fallbacks) are included, each with a comment naming the block it sits in, such as `# in: if TYPE_CHECKING`. A comment directly above a declaration stays above it, and a comment at the end of its line stays at the end; neither is ever moved to the other place.

Function bodies are replaced by the docstring, or by `...` when there is none. When a function has no docstring but has `# untyped:` or `# calls:` lines, a `...` follows them, as it would in a stub file. Defaults and constant values longer than 60 characters print as `...`.

```python
@dataclass
class Record:
    entries: list[Entry] = field(default_factory=list)
    readings: list[tuple] = field(default_factory=list)  # every candidate reading: (source, page, bbox, rows of cell text)
    errors: list[dict] = field(default_factory=list)  # readers, checks and specialists that raised: never swallowed silently
    def exclude(self, scan: str, page: int, bbox: Box, rule: str, info: str, value=None) -> None: ...
    def nominate(self, scan: str, page: int, bbox: Box, cue: str, info: str, value=None) -> None: ...

def reader_error(stage: str, page, exc: BaseException, table=None) -> None:
    """Record a reader, check or specialist that raised (stage, page or None for
    the whole paper, exception type and message).
    """
```

## Warnings and exit codes

A file that does not parse is shown as a one-line note in its section, and a warning goes to stderr as `warning: <file>: <message>`. The run goes on.

- `0`: the files were written, warnings included.
- `1`: the input cannot be used: the path does not exist, it is not a `.py` file, git cannot read the ref, or there are no Python files. The reason is printed on stderr.
- `2`: a usage error, such as a missing argument or an unknown option.

## Limits

- pysurface shows what is declared. Data held in plain dicts has no declaration, so its keys do not appear.
- Names are not resolved across modules. A type name links in the HTML when a class of that name exists anywhere in the report, the first one found by path order.
- Comments are kept only next to declarations. Comments inside function bodies are left out with the bodies.
- Calls are found statically, by name: `f()`, `module.f()`, `Class.f()`, `self.f()`, through imports anywhere in the module, including inside functions. A call through a variable, an argument, a returned object or a dynamic lookup (`obj.f()` where `obj` was built elsewhere) is not resolved and is left out rather than guessed, so the lists can be incomplete but should not be wrong. At most 12 names are shown per line, then `+N more`. The declaration diff (`--diff`) leaves calls and untyped marks out, so it shows only declaration changes.
- Instance attributes are read from `__init__` and `__post_init__` only. Attributes first set in other methods, or through `setattr`, do not appear.
- `if` and `try` blocks are followed at module level only, not inside class bodies.

## pysurface's own report

`doc/api/pysurface.api.md` and `.html` are pysurface's report on itself, regenerated whenever the code changes:

```
PYTHONPATH=src python -m pysurface src/pysurface -o doc/api --name pysurface --source-base ../../src/pysurface/
```

## Credits and license

The layout rules follow [vibelight](https://github.com/cppalliance/vibelight), which does the same for Rust crates.

License: BSL-1.0 (Boost Software License 1.0), in `LICENSE`.
