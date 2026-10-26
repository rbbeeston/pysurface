# pysurface API surface

3 modules, 4 classes, 35 functions, 2 methods, 24 fields.

## Contents

- [`__init__.py`](#init-py)
- [`__main__.py`](#main-py)
- [`core.py`](#core-py): Ids, InputError, Item, Module, anchor, args_of, call_lines, call_refs, comment_block, comment_map, count, deco_lines, ...

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
    refs: list[CallRef] = field(default_factory=list)  # calls as written (functions and methods)
    calls: list[str] = field(default_factory=list)  # resolved: quals of package functions it calls
    called_by: list[str] = field(default_factory=list)  # resolved: quals of package functions that call it
    owner: Optional[str] = None  # the enclosing class's qual, for methods

@dataclass
class Module:
    path: str
    doc: list[str]
    items: list[Item]
    hidden: int = 0
    error: str = ''
    qual: str = ''  # dotted module name from its path
    unlisted: list[Item] = field(default_factory=list)  # private names left out of the listing, kept for calls
    imports: dict[str, tuple[str, Optional[str]]] = field(default_factory=dict)

def anchor(path: str) -> str:
    # called by: render_html, render_md

def args_of(fn: FuncDef) -> str:
    # calls: short
    # called by: make_def

def call_lines(it: Item, here: str, limit: int = 12) -> list[str]:
    # calls: short_qual
    # called by: item_text

def call_refs(fn: FuncDef) -> list[CallRef]:
    """The calls a function makes, as written, in source order, each once: f(), x.f(), self.f()."""
    # called by: make_def

def comment_block(lines: list[str], indent: str) -> list[str]:
    # called by: item_text

def comment_map(src: str) -> tuple[Comments, set[int]]:
    """line -> comment text; and the set of lines that hold only a comment."""
    # called by: parse_module

def count(mods: list[Module]) -> dict[str, int]:
    # called by: render_html, render_md

def deco_lines(node: Decorated) -> list[str]:
    # called by: make_class, make_def

def doc_block(lines: list[str], indent: str) -> list[str]:
    # called by: html_lines, item_text, module_text

def docstring(node: Documented, brief: bool) -> list[str]:
    # called by: make_class, make_def, parse_module

def excluded(path: str, globs: tuple[str, ...]) -> bool:
    # called by: sources_from_dir, sources_from_git

def first_line(node: Decorated) -> int:
    # called by: make_class, make_def

def git(repo: str, *args: str) -> str:
    # calls: InputError
    # called by: sources_from_git

def html_lines(m: Module, names: dict[str, str], src_link: str | None, ids: Ids, listed: set[str]) -> str:
    """Render one module's declarations with anchors on every declaration and links on known type names."""
    # calls: doc_block, short_qual
    # called by: render_html

def imports_of(tree: ast.Module, mod_qual: str) -> dict[str, tuple[str, str | None]]:
    """Every import in the module, including ones inside functions: local name -> (module, name in
    it, or None). Relative imports are made absolute against this module's own dotted name.
    """
    # called by: parse_module

def instance_attributes(cls: ast.ClassDef, known: set[str], qual: str, comments: Comments, only: set[int]) -> list[Item]:
    """Attributes assigned as self.x in __init__ (or __post_init__), in first-assignment order."""
    # calls: short, Item, leading_comments, trailing_comment
    # called by: make_class

def item_text(it: Item, indent: str = '', here: str = '', calls: bool = True) -> list[str]:
    # calls: comment_block, doc_block, call_lines
    # called by: module_text

def leading_comments(first_line: int, comments: Comments, only: set[int]) -> list[str]:
    # called by: instance_attributes, make_class, make_def, parse_module

def link_calls(mods: list[Module]) -> None:
    """Resolve each function's calls to functions, methods and classes in this package, by name.
    Static and approximate: a call through a variable, an argument or an unknown object is left out.
    """
    # called by: load

def load(args: argparse.Namespace, ref: str | None) -> list[Module]:
    # calls: sources_from_git, sources_from_dir, InputError, parse_module, link_calls
    # called by: run

def main(argv: list[str] | None = None) -> int:
    # calls: run

def make_class(cls: ast.ClassDef, mod_qual: str, comments: Comments, only: set[int], brief: bool, context: str | None = None) -> Item:
    # calls: leading_comments, first_line, Item, deco_lines, docstring, short, trailing_comment, make_def, instance_attributes
    # called by: parse_module

def make_def(fn: FuncDef, qual: str, comments: Comments, only: set[int], brief: bool, context: str | None = None, owner: str | None = None) -> Item:
    # calls: deco_lines, args_of, leading_comments, first_line, Item, docstring, call_refs
    # called by: make_class, parse_module

def module_statements(body: list[ast.stmt], context: str | None = None) -> Iterator[tuple[ast.stmt, str | None]]:
    """Top-level statements, descending into module-level if/try blocks. Yields (node, context),
    where context names the block a definition sits in, such as "in: if TYPE_CHECKING".
    """
    # called by: parse_module

def module_text(m: Module, calls: bool = True) -> list[str]:
    # calls: doc_block, item_text
    # called by: render_diff, render_md

def parse_module(path: str, src: str, private: bool, brief: bool) -> Module:
    # calls: Module, comment_map, module_statements, make_class, make_def, short, Item, leading_comments, trailing_comment, docstring, imports_of
    # called by: load

def render_diff(old: list[Module], new: list[Module], title: str) -> str:
    # calls: module_text
    # called by: run

def render_html(mods: list[Module], title: str, src_link: str | None) -> str:
    # calls: count, anchor, Ids, html_lines
    # called by: run

def render_md(mods: list[Module], title: str, src_link: str | None) -> str:
    # calls: count, anchor, module_text
    # called by: run

def run(argv: list[str] | None) -> int:
    # calls: render_diff, load, render_md, render_html
    # called by: main

def short(node: ast.AST) -> str:
    # called by: args_of, instance_attributes, make_class, parse_module

def short_qual(q: str, here: str) -> str:
    """How a call target is written in a report: Class.method or name inside the same module,
    module.name (last path component) elsewhere.
    """
    # called by: call_lines, html_lines

def sources_from_dir(path: str, skip: tuple[str, ...]) -> dict[str, str]:
    # calls: InputError, excluded
    # called by: load

def sources_from_git(repo: str, ref: str, root: str, skip: tuple[str, ...]) -> dict[str, str]:
    """Every .py file under root at ref, read through one `git cat-file --batch` process."""
    # calls: git, excluded
    # called by: load

def trailing_comment(node: ast.stmt, comments: Comments, only: set[int]) -> str | None:
    """The comment at the end of the line where the statement ends, if that line also holds code."""
    # called by: instance_attributes, make_class, parse_module

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
- `call_lines`: [`core.py`](#core-py)
- `call_refs`: [`core.py`](#core-py)
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
- `imports_of`: [`core.py`](#core-py)
- `InputError`: [`core.py`](#core-py)
- `instance_attributes`: [`core.py`](#core-py)
- `Item`: [`core.py`](#core-py)
- `item_text`: [`core.py`](#core-py)
- `KEEP_DECOS`: [`core.py`](#core-py)
- `leading_comments`: [`core.py`](#core-py)
- `link_calls`: [`core.py`](#core-py)
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
- `short_qual`: [`core.py`](#core-py)
- `SKIP_DIRS`: [`core.py`](#core-py)
- `sources_from_dir`: [`core.py`](#core-py)
- `sources_from_git`: [`core.py`](#core-py)
- `TEST_GLOBS`: [`core.py`](#core-py)
- `trailing_comment`: [`core.py`](#core-py)
