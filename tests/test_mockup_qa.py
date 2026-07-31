"""The gate's owner-waiver path. A waiver is a statement about one photograph
(lifestyle_reading_nook's source has a top edge that wobbles sub-pixel, which
the matte faithfully reproduces), and the danger of any such mechanism is that
it turns into a way to quieten a detector - so what is pinned here is that a
waived finding still runs, still carries its measurement, and is still labelled.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import mockup_qa  # noqa: E402

FAILING = {"name": "edge-alpha-jitter", "passed": False, "detail": "p90 0.15 (limit 0.08)"}
PASSING = {"name": "fringe", "passed": True, "detail": "6267 border px clean"}


def test_waiver_unblocks_but_keeps_the_measurement():
    (f,) = mockup_qa._waive([FAILING], {"edge-alpha-jitter": "owner: source's own edge"})
    assert f["passed"] and f["waived"]
    assert "p90 0.15 (limit 0.08)" in f["detail"]      # never lost
    assert "WAIVED" in f["detail"] and "source's own edge" in f["detail"]


def test_waiver_for_another_detector_does_not_touch_this_one():
    (f,) = mockup_qa._waive([FAILING], {"fringe": "owner: something else"})
    assert not f["passed"] and "waived" not in f


def test_a_passing_finding_is_never_relabelled_as_waived():
    # Otherwise a stale waiver would silently mark a clean bundle as excused,
    # and the next reader would go looking for a defect that is not there.
    (f,) = mockup_qa._waive([PASSING], {"fringe": "owner: stale, already fixed"})
    assert f["passed"] and "waived" not in f and f["detail"] == PASSING["detail"]
