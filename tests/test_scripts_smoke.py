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


# --------------------------------------------------------------------------
# tests/fixtures/masters/ — the render harnesses must run without db/, which
# is gitignored and therefore absent on CI (PRD v3 Phase 4).
# --------------------------------------------------------------------------

FIXTURE_DIR = ROOT / "tests" / "fixtures" / "masters"


@pytest.mark.parametrize("name,ratio", [
    ("portrait-0684.png", 0.6846),
    ("landscape-1462.png", 1.4608),
    ("awkward-square.png", 1.0),
])
def test_master_fixtures_exist_at_the_expected_shape(name, ratio):
    from PIL import Image
    p = FIXTURE_DIR / name
    assert p.exists(), f"{name} missing"
    im = Image.open(p)
    assert max(im.size) == 1024
    assert abs(im.width / im.height - ratio) < 0.001


def test_both_render_harnesses_default_to_the_fixture_when_db_is_absent(monkeypatch):
    """The CI default. Neither script may need db/base_artwork/ to run."""
    import importlib
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        for mod_name, attr in (("gl19_m1_render", "REAL_MASTER"),
                               ("mockup_qa", "REAL_MASTER")):
            mod = importlib.import_module(mod_name)
            assert mod.FIXTURE.exists()
            assert mod.FIXTURE.is_relative_to(ROOT / "tests" / "fixtures")
            # if the real master is absent, the fixture is what MASTER resolves to
            if not mod.REAL_MASTER.exists():
                assert mod.MASTER == mod.FIXTURE
    finally:
        sys.path.remove(str(ROOT / "scripts"))


def test_gl19_harness_takes_an_explicit_master_path():
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import gl19_m1_render as h
        assert h.resolve_master(["--art", "x/y.png"]).name == "y.png"
    finally:
        sys.path.remove(str(ROOT / "scripts"))


def test_gelato_template_check_survives_a_cp1252_stdout(monkeypatch):
    """GL-73. A double-prime (″) in a Gelato variant title used to raise
    UnicodeEncodeError mid-report on a cp1252 console. Builds a real cp1252
    TextIOWrapper (not a mock) so the check exercises actual encoding, not a
    string match on the source."""
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import gelato_template_check as m
        wrapper = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
        monkeypatch.setattr(sys, "stdout", wrapper)
        m._ensure_utf8_stdout()
        print("25x60 cm / 10x24″ - Vertical")
    finally:
        sys.path.remove(str(ROOT / "scripts"))
