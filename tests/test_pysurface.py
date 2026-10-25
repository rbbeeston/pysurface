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
