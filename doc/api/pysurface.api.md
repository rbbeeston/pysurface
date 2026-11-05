# pysurface API surface

3 modules, 5 classes, 53 functions, 2 methods, 37 fields. Typed: 55 of 55 functions and methods (100%).

## Contents

- [`__init__.py`](#__init__-py): __version__, main, parse_module, render_diff, render_html, render_md, __all__
- [`__main__.py`](#__main__-py)
- [`core.py`](#core-py): Candidate, Ids, InputError, Item, Module, all_names, anchor, args_of, call_href, call_lines, call_refs, closest, ...

<a id="__init__-py"></a>

## `__init__.py` ([source](../../src/pysurface/__init__.py))

```python
"""pysurface: a compact, navigable report of a Python package's API surface."""

from .core import __version__
from .core import main
from .core import parse_module
from .core import render_diff
from .core import render_html
from .core import render_md

__all__ = ...
```

<a id="__main__-py"></a>

## `__main__.py` ([source](../../src/pysurface/__main__.py))

```python
# module-level code calls: core.main
```

<a id="core-py"></a>

## `core.py` ([source](../../src/pysurface/core.py))

Typed: 55 of 55 functions and methods (100%).

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
only on the declarations; --no-calls drops the calls / called-by lines;
--no-type-marks drops the untyped marks and the typed counts.

Layout rules (after vibelight, a tool that does the same for Rust):
- one section per module, in path order, opening with the module docstring;
- re-exports first (package-internal from-imports in __init__.py, and names in __all__),
  then classes sorted by name, then functions, then constants (capitals and dunders);
- every decorator is kept, since one can register a declaration (@click.command) as
  well as change it (@property);
- a class shows its bases and decorators, its docstring, fields in declared order
  (dataclass and NamedTuple field order is part of the constructor), then methods
  sorted by name, public before private;
- comments: the comment block directly above a declaration, and a comment at the
  end of a field's line, are kept with it;
- defaults and constant values longer than 60 characters print as "...";
- output is deterministic: reordering or moving code within a module leaves it
  unchanged.
"""

@dataclass
class Candidate:
    """A from-import that may be a re-export, before link_reexports decides."""
    item: Item
    base: str  # the module it imports from: dotted from the scan root when relative, as written otherwise
    relative: bool
    in_all: bool  # its name is listed in the module's __all__
    comments: list[str]  # the comment block above the statement, for its first listed name
    context: str  # the block it sits in, such as "in: try", or ""
    tail: Optional[str]  # the statement's end comment when no name has its own line, for its first listed name

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
    kind: str  # "class" | "def" | "field" | "attr" | "const" | "reexport"
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
    untyped: list[str] = field(default_factory=list)  # parameters without an annotation, and "return" if it has none
    target: Optional[str] = None  # for a re-export: the HTML id of what it names, if listed
    group: str = ''  # for a re-export: the if/try block it sits in, or ""

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
    # local name -> (module as written, name in it or None for a module import)
    reexports: list[Candidate] = field(default_factory=list)  # candidate re-exports, emptied by link_reexports
    refs: list[CallRef] = field(default_factory=list)  # calls made by module-level code, outside any def or class
    calls: list[str] = field(default_factory=list)  # resolved: quals of package functions that code calls

def all_names(tree: ast.Module) -> set[str]:
    """The strings in a module-level __all__ written as a list or tuple literal."""
    # calls: module_statements
    # called by: reexport_candidates

def anchor(path: str) -> str:
    """A module's HTML id from its path: a/_b.py is a-_b-py. Case and underscores are kept, "/"
    becomes "-", and any other character is written as ~ and six hex digits, so no two paths
    share one: _version.py and version.py, Foo.py and foo.py, a-b.py and a/b.py.
    """
    # called by: call_href, link_reexports, render_html, render_md

def args_of(fn: FuncDef) -> str:
    # calls: short
    # called by: make_def
    ...

def call_href(q: str) -> str:
    """The HTML id a call target links to: its declaration, or the module section for top-level code."""
    # calls: anchor
    # called by: html_lines

def call_lines(it: Item | Module, here: str, limit: int = 12) -> list[str]:
    """The calls and called-by comment lines of a function, or the module-level calls of a module."""
    # calls: short_qual
    # called by: item_text, module_text

def call_refs(nodes: Iterable[ast.AST]) -> list[CallRef]:
    """The calls among nodes (all of a function, or the code a module runs), as written, in source
    order, each once: f(), x.f(), self.f().
    """
    # called by: make_def, parse_module

def closest(cands: list[Module], here: Module) -> Module | None:
    """The one of several modules sharing an import name that sits nearest here: the most leading
    path components in common. None when there is none, or two are equally near.
    """
    # called by: link_reexports

def comment_block(lines: list[str], indent: str) -> list[str]:
    # called by: item_text, module_text
    ...

def comment_map(src: str) -> tuple[Comments, set[int]]:
    """line -> comment text; and the set of lines that hold only a comment."""
    # called by: parse_module

def count(mods: list[Module]) -> dict[str, int]:
    # called by: render_html, render_md
    ...

def coverage(m: Module) -> tuple[int, int]:
    """(fully annotated, all) functions and methods in a module, private and unlisted ones included."""
    # called by: render_html, render_md, total_coverage

def coverage_text(typed: int, total: int) -> str:
    """A line such as: Typed: 40 of 42 functions and methods (95%). The percentage rounds down, so 100% means all."""
    # called by: render_html, render_md

def deco_lines(node: Decorated) -> list[str]:
    """Every decorator, in source order. A decorator can change a declaration's meaning or
    register it somewhere (@click.command, @app.route, @pytest.fixture), so none are dropped.
    """
    # calls: deco_text
    # called by: make_class, make_def

def deco_text(d: ast.expr) -> str:
    """A decorator as written, with each argument longer than MAXV characters shown as "..."."""
    # calls: short
    # called by: deco_lines

def doc_block(lines: list[str], indent: str) -> list[str]:
    # called by: html_lines, item_text, module_text
    ...

def docstring(node: Documented, brief: bool) -> list[str]:
    # called by: make_class, make_def, parse_module
    ...

def excluded(path: str, globs: tuple[str, ...]) -> bool:
    # called by: sources_from_dir, sources_from_git
    ...

def executed(nodes: Iterable[ast.AST]) -> Iterator[ast.AST]:
    """Every node under nodes that runs when they run: a nested function's or lambda's body is
    skipped, its decorators and defaults are not.
    """
    # called by: parse_module

def first_line(node: Decorated) -> int:
    # called by: make_class, make_def
    ...

def gaps(items: list[Item]) -> list[bool]:
    """Whether a blank line goes before each item. Re-exports read as import blocks: the names of
    one statement stay together, a new if/try context starts a block, and a statement with a
    comment above it stands apart from its neighbours.
    """
    # called by: html_lines, module_text

def git(repo: str, *args: str) -> str:
    # calls: InputError
    # called by: sources_from_git
    ...

def html_lines(m: Module, names: dict[str, str], src_link: str | None, ids: Ids, listed: set[str], marks: bool = True) -> str:
    """Render one module's declarations with anchors on every declaration and links on known type names."""
    # calls: doc_block, call_href, short_qual, gaps
    # called by: render_html

def import_base(node: ast.ImportFrom, mod_qual: str) -> str:
    """The module a from-import reads from, made absolute against this module's own dotted name."""
    # calls: package_of
    # called by: imports_of, reexport_candidates

def import_names(mods: list[Module], root_name: str) -> dict[str, list[Module]]:
    """Each module under the dotted names an absolute import can reach it by. When the scan root is
    a package, that is the root's name and the path.
    Otherwise it is the path from the scan root, and, when the module's own directory is a package,
    the path from each directory in the unbroken run of packages above it, so a namespace package
    (google/auth/_default.py) and a src layout (src/pkg/core.py as pkg.core) both resolve. A module
    in a plain directory has only its full path, so a json.py inside a package is never json.
    A name can belong to several modules, as app.core in two services of one repository.
    """
    # called by: link_reexports

def imports_of(tree: ast.Module, mod_qual: str) -> dict[str, tuple[str, str | None]]:
    """Every import in the module, including ones inside functions: local name -> (module, name in
    it, or None). Relative imports are made absolute against this module's own dotted name.
    """
    # calls: import_base
    # called by: parse_module

def instance_attributes(cls: ast.ClassDef, known: set[str], qual: str, comments: Comments, only: set[int]) -> list[Item]:
    """Attributes assigned as self.x in __init__ (or __post_init__), in first-assignment order."""
    # calls: short, Item, leading_comments, trailing_comment
    # called by: make_class

def is_dunder(name: str) -> bool:
    """__all__, __version__ and the like: public despite the leading underscore."""
    # called by: parse_module, reexport_candidates

def item_text(it: Item, indent: str = '', here: str = '', calls: bool = True, marks: bool = True) -> list[str]:
    # calls: comment_block, call_lines, doc_block
    # called by: module_text
    ...

def leading_comments(first_line: int, comments: Comments, only: set[int]) -> list[str]:
    # called by: instance_attributes, make_class, make_def, parse_module, reexport_candidates
    ...

def link_calls(mods: list[Module]) -> None:
    """Resolve each function's calls to functions, methods and classes in this package, by name.
    Static and approximate: a call through a variable, an argument or an unknown object is left out.
    """
    # calls: module_finder
    # called by: load

def link_reexports(mods: list[Module], private: bool, root_name: str = '') -> None:
    """Turn each module's candidate re-exports into listed items, first in the module. A candidate
    is kept when it is relative, named in __all__, or an absolute import of a module in the report
    (see import_names). A kept name links to the declaration, module or further re-export it names,
    when that is in the report. Private names are counted, not shown, unless private is set.
    """
    # calls: import_names, closest, anchor
    # called by: load

def load(args: argparse.Namespace, ref: str | None) -> list[Module]:
    # calls: sources_from_git, sources_from_dir, InputError, parse_module, link_reexports, link_calls
    # called by: run
    ...

def main(argv: list[str] | None = None) -> int:
    # calls: run
    # called by: __main__.py
    ...

def make_class(cls: ast.ClassDef, mod_qual: str, comments: Comments, only: set[int], brief: bool, context: str | None = None) -> Item:
    # calls: leading_comments, first_line, Item, deco_lines, docstring, short, trailing_comment, make_def, instance_attributes
    # called by: parse_module
    ...

def make_def(fn: FuncDef, qual: str, comments: Comments, only: set[int], brief: bool, context: str | None = None, owner: str | None = None) -> Item:
    # calls: deco_lines, args_of, leading_comments, first_line, Item, docstring, call_refs, untyped_of
    # called by: make_class, parse_module
    ...

def module_finder(mods: list[Module]) -> Callable[[str], Optional[Module]]:
    """A lookup of scanned modules by dotted name. A package's __init__ answers to the package's
    name, and the top-level __init__ to "". Imports may carry the package's own name in front
    (tomd.lib.pdf.table for lib.pdf.table), so a unique suffix match also counts.
    """
    # called by: link_calls

def module_level_code(body: list[ast.stmt]) -> Iterator[ast.AST]:
    """The statements and expressions a module runs outside its functions and class bodies: plain
    statements, the tests of module-level if blocks, the bodies of try blocks and the types of
    their except clauses, and the decorators and bases of module-level classes.
    """
    # called by: parse_module

def module_statements(body: list[ast.stmt], context: str | None = None) -> Iterator[tuple[ast.stmt, str | None]]:
    """Top-level statements, descending into module-level if/try blocks. Yields (node, context),
    where context names the block a definition sits in, such as "in: if TYPE_CHECKING".
    """
    # called by: all_names, parse_module, reexport_candidates

def module_text(m: Module, calls: bool = True, marks: bool = True) -> list[str]:
    # calls: doc_block, comment_block, call_lines, gaps, item_text
    # called by: render_diff, render_md
    ...

def package_of(mod_qual: str) -> str:
    """The dotted package a module's relative imports start from: "a.b" for a.b.c and for
    a.b.__init__, and "" for a top-level module or the top-level __init__.
    """
    # called by: import_base

def parse_module(path: str, src: str, private: bool, brief: bool) -> Module:
    # calls: Module, comment_map, module_statements, make_class, make_def, is_dunder, short, Item, leading_comments, trailing_comment, docstring, imports_of, +4 more
    # called by: load
    ...

def reexport_candidates(tree: ast.Module, mod_qual: str, comments: Comments, only: set[int]) -> list[Candidate]:
    """Module-level from-imports that may be part of the API: every one in an __init__.py, and
    any whose name is listed in __all__. A name in __all__, or a dunder, is public even with a
    leading underscore.
    """
    # calls: all_names, module_statements, import_base, leading_comments, trailing_comment, is_dunder, Item, Candidate
    # called by: parse_module

def render_diff(old: list[Module], new: list[Module], title: str) -> str:
    # calls: module_text
    # called by: run
    ...

def render_html(mods: list[Module], title: str, src_link: str | None, marks: bool = True) -> str:
    # calls: count, anchor, coverage_text, total_coverage, Ids, coverage, html_lines
    # called by: run
    ...

def render_md(mods: list[Module], title: str, src_link: str | None, marks: bool = True) -> str:
    # calls: count, coverage_text, total_coverage, anchor, coverage, module_text
    # called by: run
    ...

def run(argv: list[str] | None) -> int:
    # calls: render_diff, load, render_md, render_html
    # called by: main
    ...

def short(node: ast.AST) -> str:
    # called by: args_of, deco_text, instance_attributes, make_class, parse_module
    ...

def short_qual(q: str, here: str) -> str:
    """How a call target is written in a report: Class.method or name inside the same module,
    module.name (last path component) elsewhere, and a module's path for its top-level code.
    """
    # called by: call_lines, html_lines

def sources_from_dir(path: str, skip: tuple[str, ...]) -> dict[str, str]:
    # calls: InputError, excluded
    # called by: load
    ...

def sources_from_git(repo: str, ref: str, root: str, skip: tuple[str, ...]) -> dict[str, str]:
    """Every .py file under root at ref, read through one `git cat-file --batch` process."""
    # calls: git, excluded
    # called by: load

def total_coverage(mods: list[Module]) -> tuple[int, int]:
    # calls: coverage
    # called by: render_html, render_md
    ...

def trailing_comment(node: ast.stmt, comments: Comments, only: set[int]) -> str | None:
    """The comment at the end of the line where the statement ends, if that line also holds code."""
    # called by: instance_attributes, make_class, parse_module, reexport_candidates

def untyped_of(fn: FuncDef, method: bool) -> list[str]:
    """The parameters with no annotation, in order, then "return" when the return type is missing.
    A method's self or cls is not counted, nor is __init__'s return.
    """
    # called by: make_def

CSS = ...

MAXV = 60

MODULE_CALLER = 'module:'  # a called_by entry for a module's top-level code: "module:" + the module's path

MODULE_CALLS_LABEL = 'module-level code calls'

SKIP_DIRS = ...

TEST_GLOBS = ...

__version__ = '0.2.0'
```

## Index

- `__all__`: [`__init__.py`](#__init__-py)
- `__version__`: [`__init__.py`](#__init__-py)
- `__version__`: [`core.py`](#core-py)
- `all_names`: [`core.py`](#core-py)
- `anchor`: [`core.py`](#core-py)
- `args_of`: [`core.py`](#core-py)
- `call_href`: [`core.py`](#core-py)
- `call_lines`: [`core.py`](#core-py)
- `call_refs`: [`core.py`](#core-py)
- `Candidate`: [`core.py`](#core-py)
- `closest`: [`core.py`](#core-py)
- `comment_block`: [`core.py`](#core-py)
- `comment_map`: [`core.py`](#core-py)
- `count`: [`core.py`](#core-py)
- `coverage`: [`core.py`](#core-py)
- `coverage_text`: [`core.py`](#core-py)
- `CSS`: [`core.py`](#core-py)
- `deco_lines`: [`core.py`](#core-py)
- `deco_text`: [`core.py`](#core-py)
- `doc_block`: [`core.py`](#core-py)
- `docstring`: [`core.py`](#core-py)
- `excluded`: [`core.py`](#core-py)
- `executed`: [`core.py`](#core-py)
- `first_line`: [`core.py`](#core-py)
- `gaps`: [`core.py`](#core-py)
- `git`: [`core.py`](#core-py)
- `html_lines`: [`core.py`](#core-py)
- `Ids`: [`core.py`](#core-py)
- `import_base`: [`core.py`](#core-py)
- `import_names`: [`core.py`](#core-py)
- `imports_of`: [`core.py`](#core-py)
- `InputError`: [`core.py`](#core-py)
- `instance_attributes`: [`core.py`](#core-py)
- `is_dunder`: [`core.py`](#core-py)
- `Item`: [`core.py`](#core-py)
- `item_text`: [`core.py`](#core-py)
- `leading_comments`: [`core.py`](#core-py)
- `link_calls`: [`core.py`](#core-py)
- `link_reexports`: [`core.py`](#core-py)
- `load`: [`core.py`](#core-py)
- `main`: [`__init__.py`](#__init__-py)
- `main`: [`core.py`](#core-py)
- `make_class`: [`core.py`](#core-py)
- `make_def`: [`core.py`](#core-py)
- `MAXV`: [`core.py`](#core-py)
- `Module`: [`core.py`](#core-py)
- `MODULE_CALLER`: [`core.py`](#core-py)
- `MODULE_CALLS_LABEL`: [`core.py`](#core-py)
- `module_finder`: [`core.py`](#core-py)
- `module_level_code`: [`core.py`](#core-py)
- `module_statements`: [`core.py`](#core-py)
- `module_text`: [`core.py`](#core-py)
- `package_of`: [`core.py`](#core-py)
- `parse_module`: [`__init__.py`](#__init__-py)
- `parse_module`: [`core.py`](#core-py)
- `reexport_candidates`: [`core.py`](#core-py)
- `render_diff`: [`__init__.py`](#__init__-py)
- `render_diff`: [`core.py`](#core-py)
- `render_html`: [`__init__.py`](#__init__-py)
- `render_html`: [`core.py`](#core-py)
- `render_md`: [`__init__.py`](#__init__-py)
- `render_md`: [`core.py`](#core-py)
- `run`: [`core.py`](#core-py)
- `short`: [`core.py`](#core-py)
- `short_qual`: [`core.py`](#core-py)
- `SKIP_DIRS`: [`core.py`](#core-py)
- `sources_from_dir`: [`core.py`](#core-py)
- `sources_from_git`: [`core.py`](#core-py)
- `TEST_GLOBS`: [`core.py`](#core-py)
- `total_coverage`: [`core.py`](#core-py)
- `trailing_comment`: [`core.py`](#core-py)
- `untyped_of`: [`core.py`](#core-py)
