"""GL-6 chroma model: the key's Lab locus, fitted per image
(scene_screen.key_model / key_deviation, docs/2026-07-29-gl6-chroma-model-plan.md).

The defect these guard is not hypothetical. The extractor used to decide
coverage from a pixel's Lab a/b distance to one fixed reference, so a *shadowed*
key - still 100% key - drifted away from that reference and landed in the
matte's anti-aliased ramp: 5532 px at alpha 0.87 under a vase on
lifestyle_console_vase, 847 px at alpha 0.61 under a hand's grip on
lifestyle_studio_held, while a genuine prop sat at distance 76 against the
shadow's 20-31. Both scenes now gate 8/8.

The counter-defect is just as easy to ship and much harder to see: the naive fix
(rescale each pixel's chroma by its own lightness) made the test permissive
wherever L was small, and took flat_clips_windowlight from 0 to 30 339 px of
mid-alpha. So every "the shadow stays solid" test here is paired with a "and a
dark neutral in the same shadow is still a hole" one. A model that only passes
the first half is the division again.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import scene_author as sa                            # noqa: E402
import scene_screen as ss                            # noqa: E402

KEY_RGB = (0, 177, 64)                               # scene_generate's emerald
PANEL = (100, 800, 130, 570)                         # y0 y1 x0 x1 of the synthetic panel


def _panel(shadow_to=1.0, blow_to=0.0, prop=None, patch=None):
    """A keyed panel on a pale ground, lit unevenly.

    `shadow_to` ramps the panel's brightness top to bottom (illumination falling
    off across it - the vase/finger case). `blow_to` ramps it left to right
    toward white (a specular highlight, 1.0 meaning fully clipped). `prop` and
    `patch` paint a rectangle inside the panel. Everything else - the key's
    locus, its scatter, every threshold - is derived by the model from this
    image, which is the point: there are no per-scene constants to feed it."""
    y0, y1, x0, x1 = PANEL
    rgb = np.full((900, 700, 3), 218, np.uint8)
    p = np.zeros((y1 - y0, x1 - x0, 3), np.float32) + np.float32(KEY_RGB)
    p *= np.linspace(1.0, shadow_to, y1 - y0)[:, None, None]
    if blow_to:
        b = np.linspace(0.0, blow_to, x1 - x0)[None, :, None]
        p = p * (1 - b) + 255.0 * b
    rgb[y0:y1, x0:x1] = p.round().clip(0, 255).astype(np.uint8)
    if prop is not None:
        rgb[300:420, 250:400] = prop
    if patch is not None:
        rgb[600:700, 200:350] = patch
    return rgb


def _matte(rgb):
    return sa.soft_matte(rgb, ss.key_model(rgb, KEY_RGB))


def _box(a, box):
    y0, y1, x0, x1 = box
    return a[y0:y1, x0:x1]


LIT = (150, 300, 180, 520)          # panel interior, fully lit
SHADOW = (700, 780, 180, 520)       # panel interior, deepest shadow
PROP = (310, 410, 260, 390)         # inside the prop rectangle
PATCH = (610, 690, 210, 340)        # inside the patch rectangle, in the shadow


@pytest.mark.parametrize("shadow_to", [0.5, 0.35, 0.25, 0.15])
def test_shadow_gradient_mattes_solid(shadow_to):
    """The headline case. A panel shaded to 15% of its lit brightness is still
    100% panel, and every pixel of it must print at full alpha - not the 0.61
    and 0.87 plateaus the fixed-reference test produced."""
    m = _matte(_panel(shadow_to=shadow_to))
    assert _box(m, LIT).min() == 1.0
    assert _box(m, SHADOW).min() == 1.0


def test_prop_in_shadow_is_still_a_hole():
    m = _matte(_panel(shadow_to=0.3, prop=(180, 140, 120)))
    assert _box(m, PROP).max() == 0.0
    assert _box(m, SHADOW).min() == 1.0


def test_dark_neutral_in_the_shadow_is_not_swallowed():
    """The naive division's failure mode, as a test. A near-black neutral sits
    at the same lightness as the deepest shadow and carries no key chroma at
    all; any model whose tolerance stops shrinking with the key's own chroma
    swallows it. KEY_FRAC < 1 makes that impossible by construction, at every
    lightness - a neutral's deviation *is* the locus's own magnitude."""
    m = _matte(_panel(shadow_to=0.3, patch=(28, 28, 28)))
    assert _box(m, PATCH).max() == 0.0


def test_near_key_prop_is_not_silently_swallowed():
    """The §3.2 fern, and the one place this model is measured and found *not*
    to help. A prop whose colour sits inside the key's own tolerance is
    swallowed by a locus test exactly as it was by a distance test: measured
    here, RGB (60,200,30) reads deviation 0.67 against the boundary at 1.0, so
    the mask takes it. The locus does not separate it, because the fern's
    problem was never lightness.

    What must hold is that it is not swallowed *silently*. key_contamination is
    the detector that owns this, and it has to keep firing with a shadow
    gradient in the frame - the model changes the mask that detector measures,
    so a green frond crossing the panel's edge must still show up as a
    protrusion past the panel's own straight side."""
    rgb = _panel(shadow_to=0.4)
    rgb[430:470, 540:610] = (60, 200, 30)            # crosses the panel's right edge (x=570)
    model = ss.key_model(rgb, KEY_RGB)
    assert ss.key_deviation(rgb, model)[440, 550] < 1.0       # swallowed, as before
    assert ss.key_contamination(rgb, model)["protrusion"] > 0  # but never in silence


@pytest.mark.parametrize("blow_to", [0.5, 0.8])
def test_specular_highlight_mattes_solid(blow_to):
    """The other end of the locus, and the case the corpus has no scene for
    (plan criterion 4). A hotspot washing the key 80% of the way to white takes
    its chroma from 76 Lab units down to 19; the fit follows it, because the
    panel's own pixels trace that roll-off and the second pass reaches the bins
    the first one only just missed."""
    m = _matte(_panel(blow_to=blow_to))
    assert _box(m, (150, 750, 150, 250)).min() == 1.0        # lit end
    assert _box(m, (150, 750, 500, 560)).min() == 1.0        # hot end


def test_fully_blown_highlight_is_not_recovered():
    """Stated rather than hidden: where a highlight clips to pure white the
    pixel carries no chroma at all, and no chroma model can tell it from white
    paper. It drops out of the matte. This is the model's honest boundary, and
    it is a test so that a future change which appears to "fix" it is examined
    rather than trusted - the thing it would most likely have done is make the
    tolerance permissive at high lightness, which keys the wall."""
    m = _matte(_panel(blow_to=1.0))
    assert _box(m, (150, 750, 555, 568)).max() < 1.0


def test_locus_is_recorded_and_flat_lighting_degenerates_to_one_knot():
    """Criterion 8: the fit is the bundle's provenance. A perfectly flat panel
    exhibits one lightness, so the locus is one knot - the fixed-reference test
    the old extractor did, recovered as the degenerate case rather than as a
    special case in the code."""
    flat = ss.key_model(_panel(), KEY_RGB)
    assert len(flat["knots"]) == 1
    graded = ss.key_model(_panel(shadow_to=0.3), KEY_RGB)
    assert len(graded["knots"]) > 5
    lo, hi = graded["knots"][0], graded["knots"][-1]
    assert lo[0] < hi[0]                                     # ordered by lightness
    assert np.hypot(*lo[1:]) < np.hypot(*hi[1:])             # and darker means less chroma
