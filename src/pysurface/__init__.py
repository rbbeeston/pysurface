"""pysurface: a compact, navigable report of a Python package's API surface."""
from .core import __version__, main, parse_module, render_html, render_md, render_diff

__all__ = ["__version__", "main", "parse_module", "render_html", "render_md", "render_diff"]
