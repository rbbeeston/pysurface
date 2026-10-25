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
from __future__ import annotations

import argparse
import ast
import difflib
import html
import io
import os
import re
import subprocess
import sys
import fnmatch
import time
import tokenize
from dataclasses import dataclass, field
from pathlib import Path

MAXV = 60
__version__ = "0.1.0"
TEST_GLOBS = ("tests/*", "*/tests/*", "test/*", "*/test/*", "test_*.py", "*/test_*.py", "*_test.py", "conftest.py", "*/conftest.py")
SKIP_DIRS = {"__pycache__", "node_modules", ".venv", "venv", "build", "dist", ".git", ".tox", ".nox", ".eggs"}


class InputError(Exception):
    """The input cannot be used: not a directory, file or repository, or nothing to read."""


def excluded(path: str, globs: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(path, g) for g in globs)


# ---------------------------------------------------------------- source access

def git(repo: str, *args: str) -> str:
    try:
        return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True).stdout
    except FileNotFoundError as e:
        raise InputError("git is not installed") from e
    except subprocess.CalledProcessError as e:
        raise InputError(e.stderr.strip() or f"git {' '.join(args)} failed") from e


def sources_from_git(repo: str, ref: str, root: str, skip: tuple[str, ...]) -> dict[str, str]:
    args = ["ls-tree", "-r", "--name-only", ref] + (["--", root] if root else [])
    names = [p for p in git(repo, *args).splitlines() if p.endswith(".py")]
    names = [p for p in names if not excluded(p, skip) and not (set(p.split("/")[:-1]) & SKIP_DIRS)]
    return {p: git(repo, "show", f"{ref}:{p}") for p in sorted(names)}


def sources_from_dir(path: str, skip: tuple[str, ...]) -> dict[str, str]:
    base = Path(path)
    if base.is_file():
        if base.suffix != ".py":
            raise InputError(f"{path} is not a .py file")
        return {base.name: base.read_text(encoding="utf-8", errors="replace")}
    if not base.is_dir():
        raise InputError(f"{path} does not exist")
    out = {}
    for p in sorted(base.rglob("*.py")):
        rel = p.relative_to(base)
        if any(part.startswith(".") or part in SKIP_DIRS for part in rel.parts[:-1]):
            continue
        rel_s = rel.as_posix()
        if excluded(rel_s, skip):
            continue
        out[rel_s] = p.read_text(encoding="utf-8", errors="replace")
    return out


# ---------------------------------------------------------------- model

@dataclass
class Item:
    kind: str                 # "class" | "def" | "field" | "const"
    name: str
    qual: str                 # module-qualified anchor id
    lineno: int
    text: list[str]           # declaration lines (already indented within the block)
    comments: list[str] = field(default_factory=list)
    doc: list[str] = field(default_factory=list)
    members: list["Item"] = field(default_factory=list)
    private: bool = False


@dataclass
class Module:
    path: str
    doc: list[str]
    items: list[Item]
    hidden: int = 0
    error: str = ""


def comment_map(src: str) -> tuple[dict[int, str], set[int]]:
    """line -> comment text; and the set of lines that hold only a comment."""
    comments: dict[int, str] = {}
    code_lines: set[int] = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                comments[tok.start[0]] = tok.string.lstrip("#").strip()
            elif tok.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
                                  tokenize.ENDMARKER, tokenize.ENCODING):
                for ln in range(tok.start[0], tok.end[0] + 1):
                    code_lines.add(ln)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    only = {ln for ln in comments if ln not in code_lines}
    return comments, only


def leading_comments(first_line: int, comments: dict[int, str], only: set[int]) -> list[str]:
    out = []
    ln = first_line - 1
    while ln in only:
        if comments[ln].startswith("!") or comments[ln].startswith("-*-"):
            break
        out.append(comments[ln])
        ln -= 1
    return [c for c in reversed(out) if c]


def short(node) -> str:
    s = ast.unparse(node)
    return s if len(s) <= MAXV else "..."


def docstring(node, brief: bool) -> list[str]:
    d = ast.get_docstring(node)
    if not d:
        return []
    d = d.strip()
    if brief:
        d = d.split("\n\n")[0]
        return [" ".join(l.strip() for l in d.splitlines())]
    return d.splitlines()


def args_of(fn) -> str:
    a = fn.args
    parts: list[str] = []
    pos = a.posonlyargs + a.args
    defaults = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
    for i, (arg, d) in enumerate(zip(pos, defaults)):
        s = arg.arg + (": " + ast.unparse(arg.annotation) if arg.annotation else "")
        if d is not None:
            s += (" = " if arg.annotation else "=") + short(d)
        parts.append(s)
        if a.posonlyargs and i == len(a.posonlyargs) - 1:
            parts.append("/")
    if a.vararg:
        parts.append("*" + a.vararg.arg + (": " + ast.unparse(a.vararg.annotation) if a.vararg.annotation else ""))
    elif a.kwonlyargs:
        parts.append("*")
    for arg, d in zip(a.kwonlyargs, a.kw_defaults):
        s = arg.arg + (": " + ast.unparse(arg.annotation) if arg.annotation else "")
        if d is not None:
            s += (" = " if arg.annotation else "=") + short(d)
        parts.append(s)
    if a.kwarg:
        parts.append("**" + a.kwarg.arg + (": " + ast.unparse(a.kwarg.annotation) if a.kwarg.annotation else ""))
    return ", ".join(parts)


KEEP_DECOS = ("staticmethod", "classmethod", "property", "abstractmethod", "cached_property", "overload",
              "dataclass", "dataclasses.dataclass", "contextmanager", "functools.cache", "cache", "lru_cache",
              "functools.lru_cache", "total_ordering", "runtime_checkable", "final", "unique")


def deco_lines(node) -> list[str]:
    out = []
    for d in node.decorator_list:
        s = ast.unparse(d)
        head = s.split("(")[0]
        if head in KEEP_DECOS or head.endswith((".setter", ".getter", ".deleter")):
            out.append("@" + s)
    return out


def first_line(node) -> int:
    return min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])


def make_def(fn, qual, comments, only, brief) -> Item:
    kw = "async def" if isinstance(fn, ast.AsyncFunctionDef) else "def"
    ret = " -> " + ast.unparse(fn.returns) if fn.returns else ""
    text = deco_lines(fn) + [f"{kw} {fn.name}({args_of(fn)}){ret}"]
    return Item("def", fn.name, qual, fn.lineno, text, leading_comments(first_line(fn), comments, only),
                docstring(fn, brief), private=fn.name.startswith("_") and not fn.name.endswith("__"))


def make_class(cls, mod_qual, comments, only, brief) -> Item:
    bases = ", ".join(ast.unparse(b) for b in cls.bases + list(cls.keywords))
    qual = f"{mod_qual}.{cls.name}"
    item = Item("class", cls.name, qual, cls.lineno, deco_lines(cls) + [f"class {cls.name}({bases})" if bases else f"class {cls.name}"],
                leading_comments(first_line(cls), comments, only), docstring(cls, brief),
                private=cls.name.startswith("_"))
    fields, methods, inner = [], [], []
    for node in cls.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            s = f"{node.target.id}: {ast.unparse(node.annotation)}" + (f" = {short(node.value)}" if node.value is not None else "")
            tail = comments.get(node.lineno) if node.lineno not in only else None
            fields.append(Item("field", node.target.id, f"{qual}.{node.target.id}", node.lineno, [s],
                               leading_comments(node.lineno, comments, only) + ([tail] if tail else []),
                               private=node.target.id.startswith("_")))
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            n = node.targets[0].id
            if n.startswith("__") and n.endswith("__"):
                continue
            tail = comments.get(node.lineno) if node.lineno not in only else None
            fields.append(Item("field", n, f"{qual}.{n}", node.lineno, [f"{n} = {short(node.value)}"],
                               leading_comments(node.lineno, comments, only) + ([tail] if tail else []),
                               private=n.startswith("_")))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(make_def(node, f"{qual}.{node.name}", comments, only, brief))
        elif isinstance(node, ast.ClassDef):
            inner.append(make_class(node, qual, comments, only, brief))
    methods.sort(key=lambda m: (m.private, m.name))
    item.members = [f for f in fields if not f.private] + [m for m in methods if not m.private] + \
        sorted(inner, key=lambda c: c.name) + [f for f in fields if f.private] + [m for m in methods if m.private]
    return item


def parse_module(path: str, src: str, private: bool, brief: bool) -> Module:
    mod_qual = path[:-3].replace("/", ".").replace("\\", ".")
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return Module(path, [], [], error=f"could not parse: {e.msg} (line {e.lineno})")
    comments, only = comment_map(src)
    classes, funcs, consts = [], [], []
    hidden = 0
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            c = make_class(node, mod_qual, comments, only, brief)
            if c.private and not private:
                hidden += 1
            else:
                classes.append(c)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            f = make_def(node, f"{mod_qual}.{node.name}", comments, only, brief)
            if f.private and not private:
                hidden += 1
            else:
                funcs.append(f)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            tgt = node.targets[0] if isinstance(node, ast.Assign) else node.target
            if isinstance(tgt, ast.Name) and (tgt.id.isupper() or tgt.id == "__all__") and (private or not tgt.id.startswith("_")):
                ann = f": {ast.unparse(node.annotation)}" if isinstance(node, ast.AnnAssign) else ""
                val = f" = {short(node.value)}" if node.value is not None else ""
                tail = comments.get(node.lineno) if node.lineno not in only else None
                consts.append(Item("const", tgt.id, f"{mod_qual}.{tgt.id}", node.lineno, [f"{tgt.id}{ann}{val}"],
                                   leading_comments(node.lineno, comments, only) + ([tail] if tail else [])))
    items = sorted(classes, key=lambda i: i.name) + sorted(funcs, key=lambda i: i.name) + sorted(consts, key=lambda i: i.name)
    return Module(path, docstring(tree, brief), items, hidden)


# ---------------------------------------------------------------- text rendering

def comment_block(lines: list[str], indent: str) -> list[str]:
    return [f"{indent}# {l}" if l else f"{indent}#" for l in lines]


def doc_block(lines: list[str], indent: str) -> list[str]:
    if not lines:
        return []
    if len(lines) == 1:
        return [f'{indent}"""{lines[0]}"""']
    return [f'{indent}"""{lines[0]}'] + [f"{indent}{l}" if l else "" for l in lines[1:]] + [f'{indent}"""']


def item_text(it: Item, indent: str = "") -> list[str]:
    out = comment_block(it.comments, indent) if it.kind in ("class", "def") else []
    if it.kind == "field" or it.kind == "const":
        lead = [c for c in it.comments[:-1]] if it.comments else []
        out += comment_block(lead, indent)
        tail = f"  # {it.comments[-1]}" if it.comments else ""
        return out + [indent + it.text[0] + tail]
    head = it.text[:-1]
    out += [indent + h for h in head]
    sig = it.text[-1] + ":"
    if it.kind == "def":
        body = doc_block(it.doc, indent + "    ")
        return out + [indent + sig] + body if body else out + [indent + sig + " ..."]
    out.append(indent + sig)
    out += doc_block(it.doc, indent + "    ")
    priv_started = False
    for m in it.members:
        if m.private and not priv_started:
            out.append(indent + "    # private")
            priv_started = True
        out += item_text(m, indent + "    ")
    if not it.members and not it.doc:
        out.append(indent + "    ...")
    return out


def module_text(m: Module) -> list[str]:
    if m.error:
        return [f"# {m.error}"]
    out = doc_block(m.doc, "")
    for it in m.items:
        if out:
            out.append("")
        out += item_text(it)
    if m.hidden:
        out += ["", f"# + {m.hidden} private module-level name{'s' if m.hidden != 1 else ''}"]
    return out


def count(mods: list[Module]) -> dict:
    c = {"modules": len(mods), "classes": 0, "functions": 0, "methods": 0, "fields": 0}
    for m in mods:
        for it in m.items:
            if it.kind == "class":
                c["classes"] += 1
                for mem in it.members:
                    c["methods" if mem.kind == "def" else "fields"] += 1 if mem.kind in ("def", "field") else 0
            elif it.kind == "def":
                c["functions"] += 1
    return c


def render_md(mods: list[Module], title: str, src_link: str | None) -> str:
    c = count(mods)
    out = [f"# {title}", "",
           f"{c['modules']} modules, {c['classes']} classes, {c['functions']} functions, {c['methods']} methods, {c['fields']} fields.", "",
           "## Contents", ""]
    for m in mods:
        names = ", ".join(it.name for it in m.items[:12]) + (", ..." if len(m.items) > 12 else "")
        out.append(f"- [`{m.path}`](#{anchor(m.path)}){': ' + names if names else ''}")
    out.append("")
    for m in mods:
        link = f" ([source]({src_link}{m.path}))" if src_link is not None else ""
        out += [f"## `{m.path}`{link}", "", "```python", *module_text(m), "```", ""]
    out += ["## Index", ""]
    idx = sorted({(it.name, m.path) for m in mods for it in m.items}, key=lambda t: (t[0].lower(), t[1]))
    out += [f"- `{n}`: [`{p}`](#{anchor(p)})" for n, p in idx]
    return "\n".join(out) + "\n"


def anchor(path: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-")


# ---------------------------------------------------------------- html rendering

CSS = """
:root{--bg:#fff;--fg:#1f1e1c;--mut:#6b6862;--line:#e4e1db;--side:#f7f6f2;--kw:#8a3ffc;--nm:#0f62fe;--cm:#5f7a3a;--st:#a2191f}
@media(prefers-color-scheme:dark){:root{--bg:#191817;--fg:#ecebe8;--mut:#a19d96;--line:#3a3835;--side:#211f1e;--kw:#be95ff;--nm:#78a9ff;--cm:#a7c080;--st:#ff8389}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 -apple-system,system-ui,sans-serif}
nav{position:fixed;top:0;left:0;bottom:0;width:300px;overflow:auto;background:var(--side);border-right:1px solid var(--line);padding:12px 10px;font-size:12.5px}
nav a{color:var(--fg);text-decoration:none;display:block;padding:1px 4px;border-radius:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
nav a:hover{background:var(--line)}nav .m{font-weight:600;margin-top:6px}nav .i{padding-left:16px;color:var(--mut)}
main{margin-left:300px;padding:16px 24px;max-width:1100px}h1{font-size:20px;margin:0 0 4px}h2{font-size:15px;margin:22px 0 6px;border-top:1px solid var(--line);padding-top:12px}
h2 a.src{font-weight:400;font-size:12px;color:var(--mut);margin-left:8px}.sum{color:var(--mut);margin:0 0 10px}
pre{font:12.5px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre-wrap;margin:0}
.k{color:var(--kw)}.n{color:var(--nm);font-weight:600}.c{color:var(--cm)}.d{color:var(--cm)}.c{color:var(--mut)}
a.t{color:inherit;text-decoration:underline dotted}a.ln{color:var(--mut);font-size:11px;text-decoration:none;margin-left:6px}
@media(max-width:800px){nav{position:static;width:auto;border:0}main{margin-left:0}}
"""


def html_lines(m: Module, names: dict[str, str], src_link: str | None) -> str:
    """Render one module's declarations with anchors on every declaration and links on known type names."""
    out: list[str] = []

    def link_types(s: str) -> str:
        def sub(mo):
            w = mo.group(0)
            if w in names:
                return f'<a class="t" href="#{names[w]}">{w}</a>'
            return w
        return re.sub(r"\b[A-Z][A-Za-z0-9_]+\b", sub, s)

    def emit(it: Item, indent: str) -> None:
        for c in (it.comments if it.kind in ("class", "def") else it.comments[:-1]):
            out.append(f'{indent}<span class="c"># {html.escape(c)}</span>')
        for h in it.text[:-1]:
            out.append(f'{indent}<span class="k">{html.escape(h)}</span>')
        raw = it.text[-1]
        kw = re.match(r"^(async def |def |class )?", raw).group(0)
        rest = raw[len(kw):]
        assert rest.startswith(it.name), (raw, it.name)
        tail = link_types(html.escape(rest[len(it.name):]))
        sig = (f'<span class="k">{kw}</span>' if kw else "") + f'<span class="n" id="{html.escape(it.qual)}">{html.escape(it.name)}</span>' + tail
        ln = f'<a class="ln" href="{src_link}{m.path}#L{it.lineno}">{m.path.rsplit("/", 1)[-1]}:{it.lineno}</a>' if src_link is not None else ""
        if it.kind in ("field", "const"):
            tail = f'  <span class="c"># {html.escape(it.comments[-1])}</span>' if it.comments else ""
            out.append(f"{indent}{sig}{tail}{ln}")
            return
        out.append(f"{indent}{sig}:{' ...' if it.kind == 'def' and not it.doc else ''}{ln}")
        for d in doc_block(it.doc, indent + "    "):
            out.append(f'<span class="d">{html.escape(d)}</span>')
        if it.kind == "class":
            priv = False
            for mem in it.members:
                if mem.private and not priv:
                    out.append(f'{indent}    <span class="c"># private</span>')
                    priv = True
                emit(mem, indent + "    ")
            if not it.members and not it.doc:
                out.append(f"{indent}    ...")

    if m.error:
        return f"<pre>{html.escape(m.error)}</pre>"
    for d in doc_block(m.doc, ""):
        out.append(f'<span class="d">{html.escape(d)}</span>')
    for it in m.items:
        out.append("")
        emit(it, "")
    if m.hidden:
        out += ["", f'<span class="c"># + {m.hidden} private module-level name{"s" if m.hidden != 1 else ""}</span>']
    return "<pre>" + "\n".join(out).strip("\n") + "</pre>"


def render_html(mods: list[Module], title: str, src_link: str | None) -> str:
    names: dict[str, str] = {}
    for m in mods:
        for it in m.items:
            if it.kind == "class":
                names.setdefault(it.name, it.qual)
    c = count(mods)
    nav = []
    for m in mods:
        nav.append(f'<a class="m" href="#{anchor(m.path)}">{html.escape(m.path)}</a>')
        for it in m.items:
            if it.kind in ("class", "def"):
                nav.append(f'<a class="i" href="#{it.qual}">{"class " if it.kind == "class" else ""}{html.escape(it.name)}</a>')
    body = []
    for m in mods:
        src = f'<a class="src" href="{src_link}{m.path}">source</a>' if src_link is not None else ""
        body.append(f'<h2 id="{anchor(m.path)}">{html.escape(m.path)}{src}</h2>{html_lines(m, names, src_link)}')
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{CSS}</style></head><body>
<nav><b>{html.escape(title)}</b>{''.join(nav)}</nav>
<main><h1>{html.escape(title)}</h1><p class="sum">{c['modules']} modules, {c['classes']} classes, {c['functions']} functions, {c['methods']} methods, {c['fields']} fields. Declarations, docstrings and comments only; no function bodies.</p>
{''.join(body)}</main></body></html>
"""


# ---------------------------------------------------------------- diff

def render_diff(old: list[Module], new: list[Module], title: str) -> str:
    a = {m.path: module_text(m) for m in old}
    b = {m.path: module_text(m) for m in new}
    added = [p for p in b if p not in a]
    removed = [p for p in a if p not in b]
    changed = [p for p in b if p in a and a[p] != b[p]]
    out = [f"# {title}", "", f"{len(changed)} modules changed, {len(added)} added, {len(removed)} removed; "
           f"{len([p for p in b if p in a]) - len(changed)} unchanged.", ""]
    for p in sorted(set(a) | set(b)):
        if p in a and p in b and a[p] == b[p]:
            continue
        status = "added" if p not in a else "removed" if p not in b else "changed"
        if status == "added":
            body = ["+" + l for l in b[p]]
        elif status == "removed":
            body = ["-" + l for l in a[p]]
        else:
            body = list(difflib.unified_diff(a[p], b[p], lineterm="", n=2))[2:]
        out += [f"## `{p}` ({status})", "", "```diff", *body, "```", ""]
    return "\n".join(out)


# ---------------------------------------------------------------- main

def load(args, ref: str | None) -> list[Module]:
    skip = tuple(args.exclude or ()) + (() if args.include_tests else TEST_GLOBS)
    srcs = sources_from_git(args.path, ref, args.root, skip) if ref else sources_from_dir(args.path, skip)
    if not srcs:
        raise InputError("no Python files found")
    mods = [parse_module(p, s, args.private, args.brief) for p, s in srcs.items()]
    for m in mods:
        if m.error:
            print(f"warning: {m.path}: {m.error}", file=sys.stderr)
    return mods


def main(argv: list[str] | None = None) -> int:
    try:
        return run(argv)
    except InputError as e:
        print(f"pysurface: {e}", file=sys.stderr)
        return 1


def run(argv: list[str] | None) -> int:
    ap = argparse.ArgumentParser(prog="pysurface", description=__doc__.split("\n\n")[0])
    ap.add_argument("path", help="a directory, a .py file, or (with --ref/--diff) a git repository")
    ap.add_argument("--ref", help="read the source at this git ref")
    ap.add_argument("--root", default="", help="with --ref or --diff: only paths under this directory")
    ap.add_argument("--diff", nargs=2, metavar=("OLD", "NEW"), help="print declaration changes between two refs")
    ap.add_argument("-o", "--out", default=".", help="output directory (default: current)")
    ap.add_argument("--name", help="report name (default: the directory or repo name)")
    ap.add_argument("--private", action="store_true")
    ap.add_argument("--brief", action="store_true")
    ap.add_argument("--no-source-links", action="store_true")
    ap.add_argument("--source-base", help="URL or relative path that source paths are appended to for links")
    ap.add_argument("--exclude", action="append", metavar="GLOB", help="leave out paths matching GLOB (repeatable)")
    ap.add_argument("--include-tests", action="store_true", help="keep test files (left out by default)")
    ap.add_argument("--version", action="version", version=f"pysurface {__version__}")
    a = ap.parse_args(argv)
    t0 = time.perf_counter()
    name = a.name or Path(os.path.abspath(a.path)).name
    if a.diff:
        sys.stdout.write(render_diff(load(a, a.diff[0]), load(a, a.diff[1]), f"{name}: declarations, {a.diff[0]} to {a.diff[1]}"))
        return 0
    mods = load(a, a.ref)
    if a.no_source_links:
        src = None
    elif a.source_base is not None:
        src = a.source_base
    elif a.ref:
        src = None          # git source has no local file to link to unless --source-base is given
    else:
        src = os.path.relpath(os.path.abspath(a.path if Path(a.path).is_dir() else Path(a.path).parent), os.path.abspath(a.out)) + "/"
    title = f"{name} API surface" + (f" at {a.ref}" if a.ref else "")
    os.makedirs(a.out, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", name) + (f".{re.sub(r'[^A-Za-z0-9_.-]+', '_', a.ref)}" if a.ref else "")
    md, hp = Path(a.out) / f"{stem}.api.md", Path(a.out) / f"{stem}.api.html"
    md.write_text(render_md(mods, title, src))
    hp.write_text(render_html(mods, title, src))
    print(md)
    print(hp)
    print(f"{len(mods)} modules in {time.perf_counter() - t0:.2f} s", file=sys.stderr)
    return 0
