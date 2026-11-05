import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from pysurface.core import main, parse_module, render_html, render_md, module_text

SAMPLE = textwrap.dedent('''
    """A sample module.

    It has a second paragraph.
    """
    from dataclasses import dataclass, field

    LIMIT = 10  # the most items kept
    _SECRET = 3


    # A record of one thing.
    # Second comment line.
    @dataclass
    class Thing:
        """One thing."""
        name: str  # what it is called
        size: int = 0
        tags: list[str] = field(default_factory=list)

        def grow(self, by: int = 1) -> int:
            """Grow by some amount."""
            self.size += by
            return self.size

        @property
        def label(self) -> str:
            return self.name.upper()

        def _check(self) -> bool:
            return self.size >= 0


    def make(name: str, *, size: int = 0) -> Thing:
        """Make a thing."""
        return Thing(name, size)


    def _helper():
        pass
''')


def text(src, **kw):
    return "\n".join(module_text(parse_module("pkg/sample.py", src, kw.get("private", False), kw.get("brief", False))))


def test_signatures_without_bodies():
    out = text(SAMPLE)
    assert "def make(name: str, *, size: int = 0) -> Thing:" in out
    assert "def grow(self, by: int = 1) -> int:" in out
    assert "self.size += by" not in out
    assert "return Thing" not in out


def test_docstrings_kept_in_full_or_brief():
    assert "It has a second paragraph." in text(SAMPLE)
    assert "It has a second paragraph." not in text(SAMPLE, brief=True)
    assert '"""Grow by some amount."""' in text(SAMPLE)


def test_comments_kept_with_their_declaration():
    out = text(SAMPLE)
    assert "# A record of one thing.\n# Second comment line.\n@dataclass\nclass Thing:" in out
    assert "name: str  # what it is called" in out
    assert "LIMIT = 10  # the most items kept" in out


def test_field_order_kept_and_methods_sorted():
    out = text(SAMPLE)
    assert out.index("name: str") < out.index("size: int") < out.index("tags: list[str]")
    assert out.index("def grow") < out.index("def label")


def test_private_names():
    out = text(SAMPLE)
    assert "_helper" not in out and "_SECRET" not in out
    assert "# + 1 private module-level name" in out
    assert "    # private\n    def _check(self) -> bool: ..." in out
    out = text(SAMPLE, private=True)
    assert "def _helper():\n    # untyped: return\n    ..." in out and "_SECRET = 3" in out


def test_order_and_formatting_do_not_change_output():
    reordered = textwrap.dedent('''
        """A sample module.

        It has a second paragraph.
        """
        from dataclasses import dataclass, field


        def _helper():   pass


        def make(name: str, *, size: int=0) -> Thing:
            """Make a thing."""
            x = 1
            return Thing(name, size + x - 1)


        _SECRET = 3
        LIMIT = 10  # the most items kept


        # A record of one thing.
        # Second comment line.
        @dataclass
        class Thing:
            """One thing."""
            name: str  # what it is called
            size: int = 0
            tags: list[str] = field(default_factory=list)

            def _check(self) -> bool:
                return self.size >= 0

            @property
            def label(self) -> str:
                return self.name.upper()

            def grow(self, by: int = 1) -> int:
                """Grow by some amount."""
                return self.size
    ''')
    assert text(SAMPLE) == text(reordered)


def write_pkg(root: Path):
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "__init__.py").write_text('"""The package."""\n')
    (root / "pkg" / "sample.py").write_text(SAMPLE)
    (root / "tests").mkdir()
    (root / "tests" / "test_sample.py").write_text("def test_x():\n    pass\n")
    (root / "pkg" / "broken.py").write_text("def oops(:\n")


def test_directory_run_writes_md_and_html(tmp_path, capsys):
    write_pkg(tmp_path / "src")
    out = tmp_path / "out"
    assert main([str(tmp_path / "src"), "-o", str(out), "--name", "demo"]) == 0
    md = (out / "demo.api.md").read_text()
    html = (out / "demo.api.html").read_text()
    assert "## `pkg/sample.py`" in md and "## Index" in md
    assert "test_sample" not in md                     # tests left out by default
    assert "could not parse" in md                     # a broken file is noted, not fatal
    assert "warning: pkg/broken.py" in capsys.readouterr().err
    assert "<script" not in html and "http" not in html.split("<main>")[0].split("<style>")[0]
    assert 'id="pkg.sample.Thing"' in html
    assert '<a class="t" href="#pkg.sample.Thing">Thing</a>' in html   # type names link to their class


def test_include_tests(tmp_path):
    write_pkg(tmp_path / "src")
    assert main([str(tmp_path / "src"), "-o", str(tmp_path), "--name", "d", "--include-tests"]) == 0
    assert "tests/test_sample.py" in (tmp_path / "d.api.md").read_text()


def test_no_source_links_is_byte_identical_across_runs(tmp_path):
    write_pkg(tmp_path / "src")
    for o in ("a", "b"):
        main([str(tmp_path / "src"), "-o", str(tmp_path / o), "--name", "d", "--no-source-links"])
    assert (tmp_path / "a" / "d.api.md").read_bytes() == (tmp_path / "b" / "d.api.md").read_bytes()
    assert (tmp_path / "a" / "d.api.html").read_bytes() == (tmp_path / "b" / "d.api.html").read_bytes()
    assert "source" not in (tmp_path / "a" / "d.api.md").read_text().split("## Index")[0].replace("# A sample", "")


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"})


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    (r / "lib").mkdir()
    (r / "lib" / "a.py").write_text("def f(x: int) -> int:\n    return x\n")
    git(r, "add", ".")
    git(r, "commit", "-q", "-m", "one")
    git(r, "tag", "v1")
    (r / "lib" / "a.py").write_text("def f(x: int, y: int = 0) -> int:\n    return x + y\n")
    (r / "lib" / "b.py").write_text("class New:\n    pass\n")
    git(r, "add", ".")
    git(r, "commit", "-q", "-m", "two")
    return r


def test_git_ref(repo, tmp_path):
    assert main([str(repo), "--ref", "v1", "--root", "lib", "-o", str(tmp_path), "--name", "r"]) == 0
    md = (tmp_path / "r.v1.api.md").read_text()
    assert "def f(x: int) -> int: ..." in md and "New" not in md


def test_diff_shows_declaration_changes_only(repo, capsys):
    assert main([str(repo), "--diff", "v1", "main", "--root", "lib"]) == 0
    out = capsys.readouterr().out
    assert "-def f(x: int) -> int: ..." in out
    assert "+def f(x: int, y: int = 0) -> int: ..." in out
    assert "## `lib/b.py` (added)" in out
    assert "return x + y" not in out


def test_unusable_input_exits_1(tmp_path, capsys):
    assert main([str(tmp_path / "missing")]) == 1
    assert "does not exist" in capsys.readouterr().err
    (tmp_path / "empty").mkdir()
    assert main([str(tmp_path / "empty")]) == 1


def test_module_entry_point(tmp_path):
    write_pkg(tmp_path / "src")
    r = subprocess.run([sys.executable, "-m", "pysurface", str(tmp_path / "src"), "-o", str(tmp_path / "o")],
                       capture_output=True, text=True, env={"PYTHONPATH": str(Path(__file__).parents[1] / "src")})
    assert r.returncode == 0, r.stderr
    assert re.search(r"\d+ modules in [\d.]+ s", r.stderr)


PROBE = textwrap.dedent('''
    import abc
    import sys
    import typing
    from typing import TYPE_CHECKING

    # leading only
    LEVEL = 3

    # above
    BOTH = 4  # tail


    class C:
        # leading only
        x: int = 0
        y: int = 1  # tail only
        # above y2
        y2: int = 2  # tail y2

        def __init__(self, name: str):
            # where the name goes
            self.name = name
            self._cache: dict = {}  # filled lazily
            self.name = name.upper()

        @abc.abstractmethod
        def run(self) -> None: ...

        @property
        def size(self) -> int: ...

        @size.setter
        def size(self, v: int) -> None: ...


    @typing.overload
    def g(x: int) -> int: ...
    @typing.overload
    def g(x: str) -> str: ...
    def g(x): return x


    if TYPE_CHECKING:
        def only_for_types() -> None: ...

    try:
        def shim() -> int: ...
    except ImportError:
        def shim() -> int: ...
''')


def probe_text():
    return "\n".join(module_text(parse_module("pkg/probe.py", PROBE, False, False)))


def test_leading_comment_stays_above_and_is_never_moved_to_the_tail():
    out = probe_text()
    assert "    # leading only\n    x: int = 0\n" in out
    assert "x: int = 0  #" not in out
    assert "    y: int = 1  # tail only" in out
    assert "    # above y2\n    y2: int = 2  # tail y2" in out
    assert out.endswith("# leading only\nLEVEL = 3") and "LEVEL = 3  #" not in out
    assert "# above\nBOTH = 4  # tail" in out


def test_dotted_decorators_are_kept():
    out = probe_text()
    assert "    @abc.abstractmethod\n    def run(self) -> None: ..." in out
    assert out.count("@typing.overload\ndef g(") == 2
    assert "@size.setter" in out


def test_definitions_inside_if_and_try_blocks_are_shown_with_their_context():
    out = probe_text()
    assert "# in: if TYPE_CHECKING\ndef only_for_types() -> None: ..." in out
    assert "# in: try\ndef shim() -> int: ..." in out
    assert "# in: except ImportError\ndef shim() -> int: ..." in out


def test_instance_attributes_from_init():
    out = probe_text()
    assert "    # where the name goes\n    self.name = name\n" in out
    assert out.count("self.name") == 1                      # first assignment only
    assert "    # private\n" in out and "self._cache: dict = {}  # filled lazily" in out


def test_html_ids_are_unique():
    m = parse_module("pkg/probe.py", PROBE, False, False)
    html = render_html([m], "t", None)
    ids = re.findall(r'id="([^"]+)"', html)
    assert len(ids) == len(set(ids))
    assert 'id="pkg.probe.g-2"' in html and 'id="pkg.probe.C.size-2"' in html


def test_markdown_has_explicit_anchors_for_contents_links():
    m = parse_module("pkg/probe.py", PROBE, False, False)
    md = render_md([m], "t", None)
    assert '<a id="pkg-probe-py"></a>' in md
    assert "(#pkg-probe-py)" in md


def test_css_defines_each_class_once():
    from pysurface.core import CSS
    rules = re.findall(r"(?<![\w-])\.([a-z])\{", CSS)
    assert len(rules) == len(set(rules))


def test_module_without_declarations_says_so():
    assert module_text(parse_module("m.py", "import os\n", False, False)) == ["# no declarations"]


def test_own_report_is_current():
    """doc/api must match what pysurface writes for its own source now."""
    root = Path(__file__).parents[1]
    out = root / "build" / "selfcheck"
    assert main([str(root / "src" / "pysurface"), "-o", str(out), "--name", "pysurface",
                 "--source-base", "../../src/pysurface/"]) == 0
    for ext in ("md", "html"):
        assert (out / f"pysurface.api.{ext}").read_text() == (root / "doc" / "api" / f"pysurface.api.{ext}").read_text(), \
            "regenerate doc/api (see README)"


def test_calls_and_called_by(tmp_path, capsys):
    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "util.py").write_text(textwrap.dedent('''
        def helper(x):
            return x

        class Box:
            def open(self):
                return self.peek()

            def peek(self):
                return 1
    '''))
    (pkg / "main.py").write_text(textwrap.dedent('''
        from . import util
        from .util import Box

        def run():
            b = Box()
            b.open()                 # a call through a variable: not resolved
            return util.helper(2) + _inner()

        def _inner():
            from .util import helper
            return helper(1)
    '''))
    assert main([str(tmp_path / "src"), "-o", str(tmp_path / "o"), "--name", "d", "--no-source-links"]) == 0
    md = (tmp_path / "o" / "d.api.md").read_text()
    assert "def run():\n    # untyped: return\n    # calls: util.Box, util.helper, _inner\n    ..." in md
    assert "def helper(x):\n    # untyped: x, return\n    # called by: main._inner, main.run\n    ..." in md
    assert "def open(self):\n        # untyped: return\n        # calls: Box.peek\n        ..." in md
    assert "# calls: Box.open" not in md                      # b.open() through a variable is not guessed
    html = (tmp_path / "o" / "d.api.html").read_text()
    assert '<a class="t" href="#pkg.util.helper">util.helper</a>' in html
    assert main([str(tmp_path / "src"), "-o", str(tmp_path / "p"), "--name", "d", "--no-calls"]) == 0
    assert "# calls:" not in (tmp_path / "p" / "d.api.md").read_text()


def test_every_function_in_pysurface_is_annotated():
    import ast as _ast
    src = (Path(__file__).parents[1] / "src" / "pysurface" / "core.py").read_text()
    for node in _ast.walk(_ast.parse(src)):
        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            args = [a for a in node.args.args + node.args.kwonlyargs if a.arg not in ("self", "cls")]
            missing = [a.arg for a in args if a.annotation is None]
            assert not missing and node.returns is not None, f"{node.name} lacks types: {missing or 'return'}"


def test_untyped_marks_and_coverage(tmp_path):
    src = textwrap.dedent('''
        def plain(x, *rest, key=1, **kw):
            pass

        def typed(x: int) -> int:
            return x

        class C:
            def __init__(self, a: int):
                pass

            def m(self, a: int) -> None:
                pass

            @staticmethod
            def s(a) -> None:
                pass

            def _p(self, b):
                """Private, untyped."""
    ''')
    m = parse_module("m.py", src, False, False)
    t = "\n".join(module_text(m))
    assert "def plain(x, *rest, key=1, **kw):\n    # untyped: x, *rest, key, **kw, return\n    ..." in t
    assert "def typed(x: int) -> int: ..." in t
    assert "def __init__(self, a: int): ..." in t           # self and __init__'s return are not counted
    assert "def s(a) -> None:\n        # untyped: a\n        ..." in t
    assert '"""Private, untyped."""\n        # untyped: b, return' in t   # a docstring body needs no ...
    md = render_md([m], "t", None)
    assert "Typed: 3 of 6 functions and methods (50%)." in md
    assert "# untyped" not in "\n".join(module_text(m, marks=False))
    assert "Typed:" not in render_md([m], "t", None, marks=False)
    html = render_html([m], "t", None)
    assert '<span class="c u"># untyped: x, *rest, key, **kw, return</span>' in html
    assert "Typed: 3 of 6" in html


def test_every_decorator_is_kept_with_long_arguments_shortened():
    src = textwrap.dedent('''
        import click

        @click.group()
        @click.version_option()
        def cli():
            """A tool."""

        @cli.command(name="launch", help="x" * 1)
        @click.argument("template")
        @register
        def launch(template: str) -> None:
            """Launch it."""

        @route("/a/very/long/path/that/goes/on/and/on/and/on/for/more/than/sixty/characters", methods=["GET"])
        def page() -> None: ...
    ''')
    t = "\n".join(module_text(parse_module("m.py", src, False, False)))
    assert '@click.group()\n@click.version_option()\ndef cli():' in t
    assert "@cli.command(name='launch', help='x' * 1)\n@click.argument('template')\n@register\ndef launch(template: str) -> None:" in t
    assert "@route(..., methods=['GET'])\ndef page() -> None: ..." in t


def write_files(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(text))


def test_reexports_in_init_and_all(tmp_path):
    write_files(tmp_path / "pkg", {
        "__init__.py": '''
            """The package."""
            from typing import Any
            from .core import run, Thing as T
            from . import sub
            from .core import _hidden
            from .core import *
            from pkg.core import helper
        ''',
        "core.py": '''
            from typing import Protocol
            from os.path import join
            __all__ = ["run", "Protocol"]

            class Thing: ...
            def run() -> None: ...
            def helper() -> None: ...
            def _hidden() -> None: ...
        ''',
        "sub/__init__.py": "",
    })
    assert main([str(tmp_path / "pkg"), "-o", str(tmp_path / "o"), "--name", "p", "--no-source-links"]) == 0
    md = (tmp_path / "o" / "p.api.md").read_text()
    init = md.split("## `__init__.py`")[1].split("```", 2)[1]
    assert init == ('python\n"""The package."""\n\nfrom . import sub\nfrom .core import *\nfrom .core import Thing as T\n'
                    'from .core import run\nfrom pkg.core import helper\n\n# + 1 private module-level name\n')
    core = md.split("## `core.py`")[1].split("```", 2)[1]
    assert "from typing import Protocol\n\nclass Thing" in core      # named in __all__, so listed wherever it comes from
    assert "join" not in core                                        # not in __all__ in a plain module
    assert "- [`__init__.py`](#__init__-py): sub, T, run, helper" in md   # the star import is not a name
    assert "- `T`: [`__init__.py`](#__init__-py)" in md
    html = (tmp_path / "o" / "p.api.html").read_text()
    assert '<span class="k">from .core import Thing as </span><span class="n" id="__init__.T-import"><a class="t" href="#core.Thing">T</a></span>' in html
    assert '<span class="n" id="__init__.sub-import"><a class="t" href="#sub-__init__-py">sub</a></span>' in html
    assert main([str(tmp_path / "pkg"), "-o", str(tmp_path / "q"), "--name", "p", "--private"]) == 0
    assert "from .core import _hidden" in (tmp_path / "q" / "p.api.md").read_text()


def test_module_level_calls_show_the_entry_point(tmp_path):
    write_files(tmp_path / "pkg", {
        "__main__.py": '''
            from .cli import cli

            if __name__ == "__main__":
                cli()
        ''',
        "cli.py": '''
            def cli() -> None:
                """Run."""
        ''',
    })
    assert main([str(tmp_path / "pkg"), "-o", str(tmp_path / "o"), "--name", "p", "--no-source-links"]) == 0
    md = (tmp_path / "o" / "p.api.md").read_text()
    assert "## `__main__.py`\n\n```python\n# module-level code calls: cli.cli\n```" in md
    assert 'def cli() -> None:\n    """Run."""\n    # called by: __main__.py' in md
    html = (tmp_path / "o" / "p.api.html").read_text()
    assert '# called by: </span><a class="t" href="#__main__-py">__main__.py</a>' in html
    assert '# module-level code calls: </span><a class="t" href="#cli.cli">cli.cli</a>' in html
    assert main([str(tmp_path / "pkg"), "-o", str(tmp_path / "q"), "--name", "p", "--no-calls"]) == 0
    assert "module-level code calls" not in (tmp_path / "q" / "p.api.md").read_text()


def test_reexport_resolution_is_exact(tmp_path):
    write_files(tmp_path / "pkg", {
        "__init__.py": '''
            from email.utils import formatdate
            from os import path
            from json import loads
            from pkg.utils import tidy
            from .sub import Widget
            from .sub import *
        ''',
        "utils.py": "def tidy() -> None: ...\n",
        "path.py": "",
        "json.py": "def loads() -> None: ...\n",
        "sub/__init__.py": '''
            from .impl import Widget
            from ..utils import tidy
            from ... import beyond
        ''',
        "sub/impl.py": "class Widget: ...\n",
    })
    assert main([str(tmp_path / "pkg"), "-o", str(tmp_path / "o"), "--name", "p", "--no-source-links"]) == 0
    md = (tmp_path / "o" / "p.api.md").read_text()
    init = md.split("## `__init__.py`")[1].split("```")[1]
    assert init == "python\nfrom .sub import *\nfrom .sub import Widget\nfrom pkg.utils import tidy\n"   # stdlib names are not the package's
    sub = md.split("## `sub/__init__.py`")[1].split("```")[1]
    assert sub == "python\nfrom ... import beyond\nfrom ..utils import tidy\nfrom .impl import Widget\n"
    html = (tmp_path / "o" / "p.api.html").read_text()
    assert 'id="__init__.Widget-import"><a class="t" href="#sub.impl.Widget">Widget</a>' in html   # followed through sub
    assert 'id="sub.__init__.tidy-import"><a class="t" href="#utils.tidy">tidy</a>' in html
    assert 'id="__init__.*-import"><a class="t" href="#sub-__init__-py">*</a>' in html
    assert 'id="sub.__init__.beyond-import">beyond</span>' in html                              # above the root: no link


def test_reexports_in_a_src_layout_scanned_from_above(tmp_path):
    write_files(tmp_path / "repo", {
        "src/pkg/__init__.py": "from pkg.core import helper\nfrom typing import Any\n",
        "src/pkg/core.py": "def helper() -> None: ...\n",
    })
    assert main([str(tmp_path / "repo"), "-o", str(tmp_path / "o"), "--name", "r", "--no-source-links"]) == 0
    md = (tmp_path / "o" / "r.api.md").read_text()
    assert md.split("## `src/pkg/__init__.py`")[1].split("```")[1] == "python\nfrom pkg.core import helper\n"


def test_reexport_comments_contexts_and_grouping():
    src = textwrap.dedent('''
        from .a import zed
        # The public API.
        from .core import (
            beta,   # second
            alpha,  # first one
        )
        from .b import one, two  # both
        try:
            from ._main import main
        except ImportError:
            def main() -> None: ...
        from .version import __version__
    ''')
    mods = [parse_module("__init__.py", src, False, False)]
    from pysurface.core import link_reexports
    link_reexports(mods, False)
    t = "\n".join(module_text(mods[0]))
    tail_a = "  # first one" if sys.version_info >= (3, 10) else ""
    tail_b = "  # second" if sys.version_info >= (3, 10) else ""
    assert t.startswith(
        "from .a import zed\nfrom .b import one  # both\nfrom .b import two\n\n"
        f"# The public API.\nfrom .core import alpha{tail_a}\nfrom .core import beta{tail_b}\n\n"
        "from .version import __version__\n\n"                   # a dunder is public
        "# in: try\nfrom ._main import main\n\n"                  # a context stands apart and sorts last
        "# in: except ImportError\ndef main() -> None: ...")
    html = render_html(mods, "t", None)
    assert 'id="__init__.main-import"' in html and 'id="__init__.main"' in html   # the import does not take the def's id


def test_reexport_in_plain_module_needs_all():
    m = parse_module("m.py", "from .a import x, y\nfrom ._b import _z\n__all__ = ['x', '_z']\n", False, False)
    from pysurface.core import link_reexports
    link_reexports([m], False)
    assert [i.text[0] for i in m.items if i.kind == "reexport"] == ["from ._b import _z", "from .a import x"]


def test_module_level_code_is_what_runs_at_import(tmp_path):
    write_files(tmp_path / "pkg", {
        "__main__.py": '''
            from .cli import setup, _hidden, helper, other, cli
            import contextlib

            if setup():
                with contextlib.suppress(Exception):
                    def inner():
                        helper()
                f = lambda: other()
                _hidden()
                cli()
        ''',
        "cli.py": '''
            def setup() -> bool: ...
            def helper() -> None: ...
            def other() -> None: ...
            def _hidden() -> None: ...
            def cli() -> None:
                setup()
        ''',
    })
    assert main([str(tmp_path / "pkg"), "-o", str(tmp_path / "o"), "--name", "p", "--no-source-links"]) == 0
    md = (tmp_path / "o" / "p.api.md").read_text()
    assert "# module-level code calls: cli.setup, cli._hidden, cli.cli\n" in md    # not helper or other: their bodies do not run
    assert "# called by: cli, __main__.py\n" in md                               # module callers come last
    html = (tmp_path / "o" / "p.api.html").read_text()
    assert '</span><a class="t" href="#cli.setup">cli.setup</a>, cli._hidden, <a' in html   # an unlisted target is not linked


def test_decorator_keyword_and_double_star_arguments_are_shortened():
    long = "x" * 70
    src = f"@route(path='{long}', **{{'a': '{long}'}})\ndef f() -> None: ...\n"
    t = "\n".join(module_text(parse_module("m.py", src, False, False)))
    assert "@route(path=..., **...)\ndef f() -> None: ..." in t


def test_namespace_packages_and_plain_directories(tmp_path):
    write_files(tmp_path / "root", {
        "google/auth/__init__.py": "from google.auth._default import default\nfrom auth.crypt import base\n",
        "google/auth/_default.py": "def default() -> None: ...\n",
        "google/auth/crypt/__init__.py": "from google.auth.crypt import base\n",
        "google/auth/crypt/base.py": "",
        "pkg/__init__.py": "from json import loads\nfrom typing import Any\n",
        "pkg/compat/typing.py": "",
        "scripts/json.py": "def loads() -> None: ...\n",
    })
    assert main([str(tmp_path / "root"), "-o", str(tmp_path / "o"), "--name", "r", "--no-source-links"]) == 0
    md = (tmp_path / "o" / "r.api.md").read_text()
    section = lambda p: md.split(f"## `{p}`")[1].split("```")[1]
    assert section("google/auth/__init__.py") == "python\nfrom auth.crypt import base\nfrom google.auth._default import default\n"
    assert section("google/auth/crypt/__init__.py") == "python\nfrom google.auth.crypt import base\n"
    assert section("pkg/__init__.py") == "python\n# no declarations\n"     # a plain directory's json.py is not json
    html = (tmp_path / "o" / "r.api.html").read_text()
    assert '<a class="t" href="#google.auth._default.default">default</a>' in html


def test_git_ref_with_root_lists_reexports(tmp_path):
    r = tmp_path / "repo"
    write_files(r, {
        "src/pkg/__init__.py": "from .core import run\nfrom pkg.core import helper\nfrom os import path\n",
        "src/pkg/core.py": "def run() -> None: ...\ndef helper() -> None: ...\n",
    })
    git(r, "init", "-q", "-b", "main")
    git(r, "add", ".")
    git(r, "commit", "-q", "-m", "one")
    assert main([str(r), "--ref", "HEAD", "--root", "src", "-o", str(tmp_path / "o"), "--name", "r",
                 "--source-base", "x/"]) == 0
    md = (tmp_path / "o" / "r.HEAD.api.md").read_text()
    assert md.split("## `src/pkg/__init__.py`")[1].split("```")[1] == "python\nfrom .core import run\nfrom pkg.core import helper\n"
    html = (tmp_path / "o" / "r.HEAD.api.html").read_text()
    assert '<a class="t" href="#src.pkg.core.run">run</a>' in html and '<a class="t" href="#src.pkg.core.helper">helper</a>' in html


def test_import_blocks_keep_statements_together_and_contexts_in_order():
    from pysurface.core import link_reexports
    src = textwrap.dedent('''
        from .a import c, x
        # The fast path.
        from .a import b, y
        from .m import (
            p,
        )  # closing
        if TYPE_CHECKING:
            from .t import one
            from .t import two
        try:
            from ._speed import f
        except ImportError:
            from ._slow import f
    ''')
    mods = [parse_module("__init__.py", src, False, False)]
    link_reexports(mods, False)
    t = "\n".join(module_text(mods[0]))
    assert t == ("# The fast path.\nfrom .a import b\nfrom .a import y\n\n"     # statements sort by their first name
                 "from .a import c\nfrom .a import x\nfrom .m import p" + ("  # closing" if sys.version_info >= (3, 10) else "") + "\n\n"
                 "# in: if TYPE_CHECKING\nfrom .t import one\nfrom .t import two\n\n"
                 "# in: try\nfrom ._speed import f\n\n# in: except ImportError\nfrom ._slow import f")
    assert "- [`__init__.py`](#__init__-py): b, y, c, x, p, one, two, f\n" in render_md(mods, "t", None)


def test_class_decorators_and_bases_are_module_level_code(tmp_path):
    write_files(tmp_path / "pkg", {"m.py": '''
        def register(x): return x
        def helper() -> int: return 1
        def base() -> type: return object

        @register(helper())
        class Model(base()):
            pass
    '''})
    assert main([str(tmp_path / "pkg"), "-o", str(tmp_path / "o"), "--name", "p", "--no-source-links"]) == 0
    md = (tmp_path / "o" / "p.api.md").read_text()
    assert "# module-level code calls: register, helper, base\n" in md


def test_module_anchors_are_distinct_and_dunders_are_listed():
    from pysurface.core import anchor
    assert len({anchor(p) for p in ("_version.py", "version.py", "Foo.py", "foo.py")}) == 4
    t = "\n".join(module_text(parse_module("m.py", "__all__ = ['x']\n__version__ = '1'\n_x = 2\nx = 3\n", False, False)))
    assert t == "__all__ = ['x']\n\n__version__ = '1'"


def test_package_init_keeps_its_short_name_and_shared_names_go_to_the_nearest(tmp_path):
    write_files(tmp_path / "repo", {
        "src/pkg/__init__.py": "def top() -> None: ...\n",
        "src/pkg/core.py": "def helper() -> None: ...\n",
        "src/pkg/sub/__init__.py": "from pkg import top\nfrom pkg.core import helper\n",
        "services/a/app/__init__.py": "from app.core import run\n",
        "services/a/app/core.py": "def run() -> None: ...\n",
        "services/b/app/__init__.py": "from app.core import run\n",
        "services/b/app/core.py": "def run() -> None: ...\n",
        "mylib/__init__.py": "",
        "mylib/data/tables.py": "def load() -> None: ...\n",
    })
    assert main([str(tmp_path / "repo"), "-o", str(tmp_path / "o"), "--name", "r", "--no-source-links"]) == 0
    md = (tmp_path / "o" / "r.api.md").read_text()
    section = lambda p: md.split(f"## `{p}`")[1].split("```")[1]
    assert section("src/pkg/sub/__init__.py") == "python\nfrom pkg import top\nfrom pkg.core import helper\n"
    assert section("services/b/app/__init__.py") == "python\nfrom app.core import run\n"
    html = (tmp_path / "o" / "r.api.html").read_text()
    assert 'href="#src.pkg.__init__.top">top</a>' in html
    assert 'id="services.b.app.__init__.run-import"><a class="t" href="#services.b.app.core.run">run</a>' in html


def test_plain_directory_inside_a_root_package(tmp_path):
    write_files(tmp_path / "mylib", {
        "__init__.py": "from mylib.data.tables import load\nfrom data.tables import load as bare\n",
        "data/tables.py": "def load() -> None: ...\n",
    })
    assert main([str(tmp_path / "mylib"), "-o", str(tmp_path / "o"), "--name", "m", "--no-source-links"]) == 0
    md = (tmp_path / "o" / "m.api.md").read_text()
    assert md.split("## `__init__.py`")[1].split("```")[1] == "python\nfrom mylib.data.tables import load\n"


def test_multi_line_import_closing_comment_by_python_version():
    from pysurface.core import link_reexports
    mods = [parse_module("__init__.py", "from .a import (alpha,\n    beta)  # beta is deprecated\n", False, False)]
    link_reexports(mods, False)
    t = "\n".join(module_text(mods[0]))
    if sys.version_info >= (3, 10):
        assert t == "from .a import alpha\nfrom .a import beta  # beta is deprecated"
    else:
        assert t == "from .a import alpha\nfrom .a import beta"           # no alias lines: the comment is not guessed


def test_module_anchors_never_collide():
    from pysurface.core import anchor
    paths = ["a-b.py", "a/b.py", "a b.py", "a.b.py", "_version.py", "version.py", "Foo.py", "foo.py"]
    assert len({anchor(p) for p in paths}) == len(paths)
    assert anchor("pkg/__init__.py") == "pkg-__init__-py"


def test_shared_names_ties_stars_and_submodules(tmp_path):
    write_files(tmp_path / "repo", {
        "main.py": "from app.core import run\n__all__ = ['run']\n",
        "services/a/app/__init__.py": "from app import api\nfrom app.core import *\n",
        "services/a/app/core.py": "def run() -> None: ...\n",
        "services/b/app/__init__.py": "",
        "services/b/app/api.py": "",
        "services/b/app/core.py": "def run() -> None: ...\n",
    })
    assert main([str(tmp_path / "repo"), "-o", str(tmp_path / "o"), "--name", "r", "--no-source-links"]) == 0
    html = (tmp_path / "o" / "r.api.html").read_text()
    assert 'id="main.run-import">run</span>' in html                                    # a tie: listed, not linked
    assert 'id="services.a.app.__init__.*-import"><a class="t" href="#services-a-app-core-py">*</a>' in html
    assert 'id="services.a.app.__init__.api-import">api</span>' in html               # b's api is not a's


def test_root_package_reaches_subpackages_below_a_plain_directory(tmp_path):
    write_files(tmp_path / "mylib", {
        "__init__.py": "from mylib.data.sub.x import y\nfrom mylib.data.sub import z\n",
        "data/sub/__init__.py": "def z() -> None: ...\n",
        "data/sub/x.py": "def y() -> None: ...\n",
    })
    assert main([str(tmp_path / "mylib"), "-o", str(tmp_path / "o"), "--name", "m", "--no-source-links"]) == 0
    md = (tmp_path / "o" / "m.api.md").read_text()
    assert md.split("## `__init__.py`")[1].split("```")[1] == "python\nfrom mylib.data.sub import z\nfrom mylib.data.sub.x import y\n"


def test_anchor_encodes_non_ascii_and_index_breaks_case_ties():
    from pysurface.core import anchor
    assert anchor("é.py") == "~0000e9-py"
    assert anchor("\U0001F600.py") != anchor("ὠ0.py")
    mods = [parse_module("m.py", "class Atomic: ...\ndef atomic() -> None: ...\n", False, False)]
    md = render_md(mods, "t", None)
    assert md.index("- `Atomic`") < md.index("- `atomic`")
