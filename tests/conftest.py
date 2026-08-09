"""Shared test fixtures."""

import json

import pytest
from PIL import Image

import pipeline.config as config

MASTER_ASPECT = 6656 / 9728   # db/base_artwork/39.png - the approved master


@pytest.fixture(autouse=True)
def allow_noncanonical_db(monkeypatch):
    """GL-45: every test runs against a tmp_path database, which is by definition
    not the canonical one. Tests that exercise the guard itself delete this."""
    monkeypatch.setenv("QHOTO_ALLOW_NONCANONICAL_DB", "true")


@pytest.fixture
def stub_mockup_bundles(monkeypatch, tmp_path_factory):
    """Synthetic, aspect-correct scene bundles for the gallery-rendering tests.

    The repo's four primary/portrait bundles are mid-rework (GL-6 attempt 3):
    their hand-read apertures run 0.56-0.69 against a 0.684 master, so GL-21's
    C3 cover-crop guard rejects them on purpose. These tests are about
    group_product/publish/mockup-stage logic, not scene geometry, so they get a
    stable stub rather than riding on production assets that change every
    authoring session. Real-asset coverage lives in test_mockup_render.py and in
    test_group_product's aspect-guard test.
    """
    root = tmp_path_factory.mktemp("bundles")

    def _bundle_dir(group_type, orientation, scene_id):
        d = root / group_type / orientation / scene_id
        if not d.exists():
            d.mkdir(parents=True)
            W, H, ah = 200, 300, 200
            aw = round(ah * MASTER_ASPECT)
            x0, y0 = (W - aw) // 2, 50
            Image.new("RGBA", (W, H), (180, 170, 160, 255)).save(d / "background.png")
            Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(d / "overlay.png")
            (d / "meta.json").write_text(json.dumps({
                "scene": scene_id, "group_type": group_type, "orientation": orientation,
                "aperture": [[x0, y0], [x0 + aw, y0], [x0 + aw, y0 + ah], [x0, y0 + ah]],
                "size": [W, H],
                "tag": "flat" if scene_id.startswith("flat") else "lifestyle",
                "overfill": 0.0,
            }))
        return d

    monkeypatch.setattr(config, "mockup_bundle_dir", _bundle_dir)
    return root
