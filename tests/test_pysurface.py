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
    assert "def _helper(): ..." in out and "_SECRET = 3" in out


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
