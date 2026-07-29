"""GL-6 P4b intake tool. Guards the one thing standing between a hand-generated
Nano Banana PNG dropped into assets/mockups/inflow/ and an authored, gated
bundle: that intake refuses without provenance, stops before extract on an
aspect that authoring can never fix, never touches assets/ in --dry-run, and
that the sidecar's key_rgb_requested spelling actually reaches scene.json as
key_rgb (silently dropping that normalisation switches key-spill off on every
hand-made scene - see scene_intake._normalise_provenance).

Also covers scene_screen.key_contamination: the pivot doc §3.2 defect (a fern
frond near-key enough to be swallowed into the mask) that mask-solidity alone
provably cannot see.
"""

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import scene_intake                                 # noqa: E402
import scene_screen as ss                            # noqa: E402

KEY_RGB = (0, 177, 64)


def _panel_image(path: Path, canvas=(1600, 2200), aspect=0.6869, area_frac=0.15,
                  key_rgb=KEY_RGB):
    """A synthetic keyed panel at `aspect`, sized to land inside AREA_RANGE, at
    the primary group's own printed-range midpoint by default - the same card
    the pivot doc's geometry cards use, so the screen's aspect check passes."""
    cw, ch = canvas
    area = area_frac * cw * ch
    ph = round((area / aspect) ** 0.5)
    pw = round(ph * aspect)
    rgb = np.full((ch, cw, 3), 235, np.uint8)
    x0, y0 = (cw - pw) // 2, (ch - ph) // 2
    rgb[y0:y0 + ph, x0:x0 + pw] = key_rgb
    Image.fromarray(rgb).save(path)
    return pw, ph


def _sidecar(path: Path, **overrides):
    body = {
        "model": "google/nano-banana-pro", "prompt": "test scene",
        "generated_at": "2026-07-29", "key_rgb_requested": list(KEY_RGB),
        "generated_via": "Replicate playground (manual)",
    }
    body.update(overrides)
    path.write_text(json.dumps(body))


# extract() records source_image relative to ROOT (so a bundle's provenance
# resolves on anyone's checkout, per scene_author's own comment) - it hard-
# requires the source to actually live under ROOT, which pytest's tmp_path
# (system temp, outside the repo) is not. Stage under outputs/, which is
# git-ignored, instead of assets/ itself.
INTAKE_TMP = ROOT / "outputs" / "_test_scene_intake"


def _make_scene(tmp_path, group_dirname="primary", stem="lifestyle_test",
                 aspect=0.6869, sidecar=True, **sidecar_overrides):
    """A source image + sidecar under tmp_path/<group_dirname>/, mirroring
    assets/mockups/inflow/<group>/ layout so group resolves from the folder name."""
    d = tmp_path / group_dirname
    d.mkdir(parents=True, exist_ok=True)
    img = d / f"{stem}.png"
    _panel_image(img, aspect=aspect)
    if sidecar:
        _sidecar(d / f"{stem}.json", **sidecar_overrides)
    return img


@pytest.fixture
def tmp_path(tmp_path):
    """Override pytest's own tmp_path with a repo-local one (see INTAKE_TMP
    above) - every test in this file uses this fixture name unmodified."""
    import shutil
    d = INTAKE_TMP / tmp_path.name
    d.mkdir(parents=True, exist_ok=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)


# --------------------------------------------------------------------------- intake

def test_missing_sidecar_refuses_to_run(tmp_path):
    img = _make_scene(tmp_path, sidecar=False)
    rc = scene_intake.main(["scene_intake.py", str(img), "--dry-run"])
    assert rc != 0
    assert not (ROOT / "outputs" / "scene_intake" / img.stem).exists()


def test_missing_required_key_names_it(tmp_path, capsys):
    img = _make_scene(tmp_path)
    (img.with_suffix(".json")).write_text(json.dumps({"prompt": "test"}))  # no generated_via/key
    rc = scene_intake.main(["scene_intake.py", str(img), "--dry-run"])
    out = capsys.readouterr().out
    assert rc != 0
    assert "generated_via" in out


def test_null_model_prompt_and_date_warn_but_do_not_refuse(tmp_path, capsys):
    """The four shipped scenes' sidecars record model/prompt/generated_at as null -
    honestly, because no manifest ever held them and one of the four is an
    ordinary photograph. An intake that refuses those refuses the truth, and the
    owner's next move would be to invent a plausible value to get past it."""
    img = _make_scene(tmp_path, model=None, prompt=None, generated_at=None,
                      generated_via="P0 batch, seed 22")
    rc = scene_intake.main(["scene_intake.py", str(img), "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "WARN" in out and "generated_at" in out
    sj = json.loads(next((ROOT / "outputs" / "scene_intake" / img.stem).rglob("scene.json")).read_text())
    assert sj["model"] is None and sj["prompt"] is None


def test_no_key_colour_points_at_the_seeded_path(tmp_path, capsys):
    """A keyless sidecar must not fall through to extract's emerald default and
    key whatever in the photograph happens to be greenish."""
    img = _make_scene(tmp_path, key=None, key_rgb_requested=None)
    rc = scene_intake.main(["scene_intake.py", str(img), "--dry-run"])
    out = capsys.readouterr().out
    assert rc != 0
    assert "--seeded" in out
    assert not (ROOT / "outputs" / "scene_intake" / img.stem).exists()


def test_group_resolves_from_inflow_folder_name(tmp_path):
    img = _make_scene(tmp_path, group_dirname="5x7", aspect=0.7143)
    rc = scene_intake.main(["scene_intake.py", str(img), "--dry-run"])
    assert rc == 0
    bundle_dirs = list((ROOT / "outputs" / "scene_intake" / img.stem).rglob("scene.json"))
    assert bundle_dirs, "extract never ran"
    assert json.loads(bundle_dirs[0].read_text())["group_type"] == "5x7"


def test_aspect_failure_stops_before_extract(tmp_path):
    # primary panel aspect on a 10x24 target (0.4167) - nowhere near the range,
    # exactly P4b1's structural failure (pivot doc §1.1)
    img = _make_scene(tmp_path, group_dirname="10x24", aspect=0.6869)
    rc = scene_intake.main(["scene_intake.py", str(img), "--dry-run"])
    assert rc != 0
    assert not (ROOT / "outputs" / "scene_intake" / img.stem).exists()


def test_dry_run_writes_nothing_under_assets(tmp_path):
    img = _make_scene(tmp_path)
    before = {p for p in (ROOT / "assets" / "mockups").rglob("*") if p.is_file()}
    rc = scene_intake.main(["scene_intake.py", str(img), "--dry-run"])
    after = {p for p in (ROOT / "assets" / "mockups").rglob("*") if p.is_file()}
    assert rc == 0
    assert before == after


def test_sidecar_fields_land_in_scene_json_with_normalised_key_rgb(tmp_path):
    img = _make_scene(tmp_path, model="google/nano-banana-pro", prompt="a bench and a fern")
    rc = scene_intake.main(["scene_intake.py", str(img), "--dry-run"])
    assert rc == 0
    sj_path = next((ROOT / "outputs" / "scene_intake" / img.stem).rglob("scene.json"))
    sj = json.loads(sj_path.read_text())
    assert sj["model"] == "google/nano-banana-pro"
    assert sj["prompt"] == "a bench and a fern"
    # the sidecar only ever writes key_rgb_requested; scene.json must carry the
    # normalised key_rgb too, or d_key_spill reports "n/a" on every hand-made scene
    assert sj["key_rgb"] == list(KEY_RGB)


# --------------------------------------------------------------------------- replicate export

def _replicate_sidecar(**overrides):
    """A raw Replicate prediction export, in miniature - the owner's real
    hand-run artefact (downloaded from the playground), not our _TEMPLATE.json.
    Built in-test rather than copied from the owner's real scene-1 file."""
    body = {
        "id": "3m3ccmrjtxrmr0czntdrjcwg18", "status": "succeeded",
        "created_at": "2026-07-29T16:00:26Z", "completed_at": "2026-07-29T16:00:56Z",
        "input": {
            "prompt": "a test prompt", "resolution": "2K",
            "image_input": ["https://replicate.delivery/x/geometry_card_primary_0.6869.png"],
            "aspect_ratio": "4:3", "output_format": "png",
        },
        "urls": {"web": "https://replicate.com/p/3m3ccmrjtxrmr0czntdrjcwg18"},
        "version": "hidden",
    }
    body.update(overrides)
    return body


def _make_replicate_scene(tmp_path, group_dirname="primary",
                          stem="replicate-prediction-3m3ccmrjtxrmr0czntdrjcwg18",
                          aspect=0.6869, sidecar_overrides=None):
    d = tmp_path / group_dirname
    d.mkdir(parents=True, exist_ok=True)
    img = d / f"{stem}.png"
    _panel_image(img, aspect=aspect)
    (d / f"{stem}.json").write_text(json.dumps(_replicate_sidecar(**(sidecar_overrides or {}))))
    return img


def test_replicate_export_authors_and_carries_input_body(tmp_path):
    img = _make_replicate_scene(tmp_path)
    rc = scene_intake.main(["scene_intake.py", str(img), "--dry-run", "--name", "lifestyle_repl_test"])
    assert rc == 0
    sj_path = next((ROOT / "outputs" / "scene_intake" / "lifestyle_repl_test").rglob("scene.json"))
    sj = json.loads(sj_path.read_text())
    assert sj["prompt"] == "a test prompt"
    assert sj["input"]["resolution"] == "2K"          # the whole input body, unflattened
    assert sj["prediction_id"] == "3m3ccmrjtxrmr0czntdrjcwg18"
    assert sj["key_rgb"] == list(KEY_RGB)
    assert sj["model"] == "google/nano-banana-pro"
    assert "not name the model" in sj["model_source"]  # defaulted, never mistaken for read


def test_replicate_export_non_succeeded_refuses(tmp_path):
    img = _make_replicate_scene(tmp_path, sidecar_overrides={"status": "failed"})
    rc = scene_intake.main(["scene_intake.py", str(img), "--dry-run", "--name", "lifestyle_repl_fail"])
    assert rc != 0
    assert not (ROOT / "outputs" / "scene_intake" / "lifestyle_repl_fail").exists()


def test_replicate_export_card_group_mismatch_refuses(tmp_path):
    # image sits in the 5x7 folder but the attached geometry card is for primary
    img = _make_replicate_scene(tmp_path, group_dirname="5x7", aspect=0.7143)
    rc = scene_intake.main(["scene_intake.py", str(img), "--dry-run", "--name", "lifestyle_repl_mismatch"])
    assert rc != 0
    assert not (ROOT / "outputs" / "scene_intake" / "lifestyle_repl_mismatch").exists()


def test_replicate_export_missing_card_without_key_refuses(tmp_path):
    img = _make_replicate_scene(tmp_path, sidecar_overrides={
        "input": {"prompt": "no card here", "image_input": []}})
    rc = scene_intake.main(["scene_intake.py", str(img), "--dry-run", "--name", "lifestyle_repl_nokey"])
    assert rc != 0
    assert not (ROOT / "outputs" / "scene_intake" / "lifestyle_repl_nokey").exists()


def test_replicate_export_stem_without_name_refuses(tmp_path):
    img = _make_replicate_scene(tmp_path)
    rc = scene_intake.main(["scene_intake.py", str(img), "--dry-run"])   # no --name given
    assert rc != 0


@pytest.fixture(autouse=True)
def _cleanup_outputs():
    yield
    import shutil
    d = ROOT / "outputs" / "scene_intake"
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


# --------------------------------------------------------------------------- key_contamination

def _keyed_canvas(w=400, h=560, key=KEY_RGB):
    rgb = np.full((h, w, 3), 235, np.uint8)
    rgb[40:520, 60:340] = key
    return rgb


def test_key_contamination_silent_on_clean_panel():
    rgb = _keyed_canvas()
    c = ss.key_contamination(rgb, ss.key_model(rgb, KEY_RGB))
    assert c["protrusion"] == 0
    assert c["intrusion"] == 0


def test_key_contamination_fires_on_near_key_frond():
    """A near-key-coloured frond crossing the panel's right edge: outside the
    quad it is close enough to the key to be mask-classified (protrusion), and
    a separate near-key blob well inside the panel lands in the 1x-2.5x
    tolerance band (intrusion) - the two measurements mask-solidity cannot make,
    because solidity only ever looks at the panel's largest filled component."""
    rgb = _keyed_canvas()
    # crosses the panel's right edge (x=340) with a colour ~20 Lab units from
    # the key - inside KEY_LAB_TOL=32, so mask-classified where it pokes outside
    cv2.line(rgb, (300, 200), (380, 260), (60, 200, 30), 14, cv2.LINE_AA)
    # isolated, well inside the panel and away from its own rim - a colour
    # ~40 Lab units out, inside the 32-80 intrusion band
    cv2.circle(rgb, (150, 150), 10, (200, 220, 90), -1)
    c = ss.key_contamination(rgb, ss.key_model(rgb, KEY_RGB))
    assert c["protrusion"] > 0
    assert c["intrusion"] > 0
    assert c["clusters"]
