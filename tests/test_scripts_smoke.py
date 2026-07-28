"""GL-21 P3.5/F1. The authoring scripts have no test suite of their own - they
are tools, not pipeline code - so nothing noticed that `scripts/mockup_qa.py`
did not *parse* below Python 3.12. It nested same-quote f-strings (PEP 701), a
hard SyntaxError on 3.10/3.11: the gate that stands between ~26 P4 bundles and
an owner review never ran at all there, and the repo declared no floor to
measure that against.

Two checks, because neither alone is enough:

  imports  every script must import cleanly on the interpreter running the
           suite - catches a broken import, a module-level typo, a renamed
           helper.
  floor    every script and pipeline module must be parseable on the floor
           `pyproject.toml` declares, which the running interpreter is *not*
           required to be. `ast.parse(..., feature_version=(3, 10))` does not
           reject PEP 701 (verified), and `compile` uses the running grammar,
           so the construct is detected directly off the token stream.
"""

import importlib
import io
import re
import sys
import token
import tokenize
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = sorted((ROOT / "scripts").glob("*.py"))
SOURCES = SCRIPTS + sorted((ROOT / "pipeline").glob("*.py"))


def python_floor() -> tuple[int, int]:
    """The declared floor, read straight out of pyproject (tomllib is 3.11+, and
    the floor is below that)."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'requires-python\s*=\s*"[^\d]*(\d+)\.(\d+)"', text)
    assert m, "pyproject.toml must declare requires-python"
    return int(m[1]), int(m[2])


def _delim(tok: tokenize.TokenInfo) -> str:
    """The quote sequence a string/f-string token opens with, prefix stripped."""
    s = tok.string.lstrip("fFrRbBuU")
    return s[:3] if s[:3] in ('"""', "'''") else s[:1]


def same_quote_nesting(src: str) -> list[tuple[int, int]]:
    """Positions of strings nested inside an f-string using that f-string's own
    quote sequence - legal from 3.12, a SyntaxError before it.

    Only 3.12 tokenizes f-strings into parts (FSTRING_START/MIDDLE/END); on an
    older interpreter an f-string is one opaque STRING token, but there a bad
    file fails to import anyway, which the other check already catches."""
    fstring_start = getattr(token, "FSTRING_START", None)
    if fstring_start is None:
        return []
    found, open_delims = [], []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type in (fstring_start, token.STRING):
            if _delim(tok) in open_delims:
                found.append(tok.start)
        if tok.type == fstring_start:
            open_delims.append(_delim(tok))
        elif tok.type == token.FSTRING_END and open_delims:
            open_delims.pop()
    return found


@pytest.mark.parametrize("path", SCRIPTS, ids=lambda p: p.name)
def test_script_imports(path):
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        importlib.import_module(path.stem)
    finally:
        sys.path.remove(str(ROOT / "scripts"))


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_parses_on_declared_floor(path):
    if python_floor() >= (3, 12):
        pytest.skip("floor is 3.12+, PEP 701 is available")
    bad = same_quote_nesting(path.read_text(encoding="utf-8"))
    assert not bad, (
        f"{path.name} nests same-quote f-strings at {bad} - PEP 701, 3.12+ only, "
        f"but pyproject declares {python_floor()}"
    )


def test_the_floor_check_can_see_the_defect():
    """The line F1 actually shipped. A detector that cannot see a known defect
    is not a detector (mockup_qa.demo's rule, applied to the suite)."""
    assert same_quote_nesting("""print(f"-> {sheet(out / f'{r['scene']}.png')}")""")
    assert not same_quote_nesting("""print(f"-> {sheet(out / (r['scene'] + '.png'))}")""")
    assert not same_quote_nesting("""x = f'''{d['k']}'''""")   # differing delimiters: fine
