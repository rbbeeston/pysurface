# pysurface API surface

3 modules, 4 classes, 30 functions, 2 methods, 17 fields.

## Contents

- [`__init__.py`](#init-py)
- [`__main__.py`](#main-py)
- [`core.py`](#core-py): Ids, InputError, Item, Module, anchor, args_of, comment_block, comment_map, count, deco_lines, doc_block, docstring, ...

<a id="init-py"></a>

## `__init__.py` ([source](../../src/pysurface/__init__.py))

```python
"""pysurface: a compact, navigable report of a Python package's API surface."""
```

<a id="main-py"></a>

## `__main__.py` ([source](../../src/pysurface/__main__.py))

```python
# no declarations
```

<a id="core-py"></a>

## `core.py` ([source](../../src/pysurface/core.py))

```python
"""pysurface: a compact, navigable report of a Python package's API surface.

Reads Python source (a directory, or a git ref of a repository) without importing
or running it, and writes one Markdown file and one self-contained HTML file:
every module, class, field, method, function and constant, with signatures,
docstrings and the comments written beside the code, and no bodies.

Built for people and language models that need the shape of a codebase quickly:
one file to read instead of dozens of source files to open. No AI, no network,
no imports of the package, so it runs in a second or two on a large package.

  pysurface PATH [-o OUT] [--name NAME]          # a directory or a .py file
  pysurface REPO --ref REF [--root lib] [-o OUT]   # a git ref, read with git show
  pysurface REPO --diff OLD NEW [--root lib]       # declaration changes only

Options: --private keeps module-level private names (inner private members of a
class are always kept, under "# private"); --brief keeps only the first paragraph
of each docstring; --no-source-links drops file:line links, so the output depends
only on the declarations.

Layout rules (after vibelight, a tool that does the same for Rust):
- one section per module, in path order, opening with the module docstring;
- classes first, sorted by name; then functions; then constants;
- a class shows its bases and decorators, its docstring, fields in declared order
  (dataclass and NamedTuple field order is part of the constructor), then methods
  sorted by name, public before private;
- comments: the comment block directly above a declaration, and a comment at the
  end of a field's line, are kept with it;
- defaults and constant values longer than 60 characters print as "...";
- output is deterministic: reordering or moving code within a module leaves it
  unchanged.
"""

class Ids:
    """Unique HTML ids: a repeated name (an overload, a property's setter, a definition in both
    branches of an if) gets a -2, -3 ... suffix in document order.
    """
    self.seen: dict[str, int] = {}
    self.first: dict[str, str] = {}
    def __call__(self, qual: str) -> str: ...
    def __init__(self) -> None: ...

class InputError(Exception):
    """The input cannot be used: not a directory, file or repository, or nothing to read."""

@dataclass
class Item:
    kind: str  # "class" | "def" | "field" | "attr" | "const"
    name: str
    qual: str  # module-qualified anchor id (made unique when rendered)
    lineno: int
    text: list[str]  # declaration lines: kept decorators, then the declaration itself
    lead: list[str] = field(default_factory=list)  # the comment block directly above
    tail: str | None = None  # the comment at the end of the declaration's own line
    doc: list[str] = field(default_factory=list)
    members: list['Item'] = field(default_factory=list)
    private: bool = False

@dataclass
class Module:
    path: str
    doc: list[str]
    items: list[Item]
    hidden: int = 0
    error: str = ''

def anchor(path: str) -> str: ...

def args_of(fn) -> str: ...

def comment_block(lines: list[str], indent: str) -> list[str]: ...

def comment_map(src: str) -> tuple[dict[int, str], set[int]]:
    """line -> comment text; and the set of lines that hold only a comment."""

def count(mods: list[Module]) -> dict: ...

def deco_lines(node) -> list[str]: ...

def doc_block(lines: list[str], indent: str) -> list[str]: ...

def docstring(node, brief: bool) -> list[str]: ...

def excluded(path: str, globs: tuple[str, ...]) -> bool: ...

def first_line(node) -> int: ...

def git(repo: str, *args: str) -> str: ...

def html_lines(m: Module, names: dict[str, str], src_link: str | None, ids: Ids) -> str:
    """Render one module's declarations with anchors on every declaration and links on known type names."""

def instance_attributes(cls, known: set[str], qual: str, comments, only) -> list[Item]:
    """Attributes assigned as self.x in __init__ (or __post_init__), in first-assignment order."""

def item_text(it: Item, indent: str = '') -> list[str]: ...

def leading_comments(first_line: int, comments: dict[int, str], only: set[int]) -> list[str]: ...

def load(args, ref: str | None) -> list[Module]: ...

def main(argv: list[str] | None = None) -> int: ...

def make_class(cls, mod_qual, comments, only, brief, context=None) -> Item: ...

def make_def(fn, qual, comments, only, brief, context=None) -> Item: ...

def module_statements(body, context=None):
    """Top-level statements, descending into module-level if/try blocks. Yields (node, context),
    where context names the block a definition sits in, such as "in: if TYPE_CHECKING".
    """

def module_text(m: Module) -> list[str]: ...

def parse_module(path: str, src: str, private: bool, brief: bool) -> Module: ...

def render_diff(old: list[Module], new: list[Module], title: str) -> str: ...

def render_html(mods: list[Module], title: str, src_link: str | None) -> str: ...

def render_md(mods: list[Module], title: str, src_link: str | None) -> str: ...

def run(argv: list[str] | None) -> int: ...

def short(node) -> str: ...

def sources_from_dir(path: str, skip: tuple[str, ...]) -> dict[str, str]: ...

def sources_from_git(repo: str, ref: str, root: str, skip: tuple[str, ...]) -> dict[str, str]:
    """Every .py file under root at ref, read through one `git cat-file --batch` process."""

def trailing_comment(node, comments: dict[int, str], only: set[int]) -> str | None:
    """The comment at the end of the line where the statement ends, if that line also holds code."""

CSS = ...

# Decorators that change what a declaration means. Matched on the last dotted component,
# so @abc.abstractmethod, @typing.overload and @functools.lru_cache(...) are kept too.
KEEP_DECOS = ...

MAXV = 60

SKIP_DIRS = ...

TEST_GLOBS = ...
```

## Index

- `anchor`: [`core.py`](#core-py)
- `args_of`: [`core.py`](#core-py)
- `comment_block`: [`core.py`](#core-py)
- `comment_map`: [`core.py`](#core-py)
- `count`: [`core.py`](#core-py)
- `CSS`: [`core.py`](#core-py)
- `deco_lines`: [`core.py`](#core-py)
- `doc_block`: [`core.py`](#core-py)
- `docstring`: [`core.py`](#core-py)
- `excluded`: [`core.py`](#core-py)
- `first_line`: [`core.py`](#core-py)
- `git`: [`core.py`](#core-py)
- `html_lines`: [`core.py`](#core-py)
- `Ids`: [`core.py`](#core-py)
- `InputError`: [`core.py`](#core-py)
- `instance_attributes`: [`core.py`](#core-py)
- `Item`: [`core.py`](#core-py)
- `item_text`: [`core.py`](#core-py)
- `KEEP_DECOS`: [`core.py`](#core-py)
- `leading_comments`: [`core.py`](#core-py)
- `load`: [`core.py`](#core-py)
- `main`: [`core.py`](#core-py)
- `make_class`: [`core.py`](#core-py)
- `make_def`: [`core.py`](#core-py)
- `MAXV`: [`core.py`](#core-py)
- `Module`: [`core.py`](#core-py)
- `module_statements`: [`core.py`](#core-py)
- `module_text`: [`core.py`](#core-py)
- `parse_module`: [`core.py`](#core-py)
- `render_diff`: [`core.py`](#core-py)
- `render_html`: [`core.py`](#core-py)
- `render_md`: [`core.py`](#core-py)
- `run`: [`core.py`](#core-py)
- `short`: [`core.py`](#core-py)
- `SKIP_DIRS`: [`core.py`](#core-py)
- `sources_from_dir`: [`core.py`](#core-py)
- `sources_from_git`: [`core.py`](#core-py)
- `TEST_GLOBS`: [`core.py`](#core-py)
- `trailing_comment`: [`core.py`](#core-py)
