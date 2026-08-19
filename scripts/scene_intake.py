"""GL-6 P4b intake: one hand-generated inflow image -> an authored, gated bundle.

Nano Banana Pro scenes are hand-run into `assets/mockups/inflow/<group>/`
(docs/2026-07-29-p4b-scene-generation-pivot.md §4) - there is no batch harness
generating them, so nothing else stands between a dropped-in PNG and a bundle
an owner can review. This is that one command: sidecar -> screen -> key-
collision warning -> extract -> gate -> contact sheet, hard-stopping at the
first failure that makes a later stage meaningless.

    scene_intake.py assets/mockups/inflow/primary/lifestyle_bench_fern.png
                    [--dry-run] [--group primary|5x7|10x24] [--orientation O]
                    [--model MODEL_ID] [--key emerald|magenta] [--name SCENE]
                    [--tag flat|lifestyle] [--force]

--force authors past a *non-aspect* screen failure and past a geometry card that
names another group (a miss can land inside a different group's printed range).
`aspect` itself is never forceable: it is the one thing about the pixels that no
authoring changes. The gate still decides, and the waived check is still printed.

--dry-run authors into outputs/scene_intake/<scene>/bundle/ instead of
assets/mockups/ - same extract(), same gate, nothing written under assets/.

The sidecar may be EITHER shape:
  our own _TEMPLATE.json (model/prompt/key.../generated_at at top level), or
  a raw Replicate prediction export downloaded from the playground - the
  owner's actual hand-run artefact, and richer than our template (exact input
  body, prediction id, timings). Detected by id+status+input all present at
  the top level, which our template never has. See _handle_replicate_export.
"""

import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import corpus_backup                                # noqa: E402
import mockup_qa                                    # noqa: E402
import scene_author                                 # noqa: E402
import scene_generate                               # noqa: E402
import scene_screen as ss                           # noqa: E402

REQUIRED_SIDECAR_KEYS = ("generated_via",)   # how the image came about, and nothing
                                             # narrower: model/prompt/seed are null for
                                             # flat_leaning_bookstack, which is an ordinary
                                             # photograph, and generated_at is null for
                                             # every pre-P4b scene because no manifest ever
                                             # recorded one. Requiring those made the tool
                                             # refuse the four scenes already shipped - a
                                             # sidecar's job is to say *honestly* where the
                                             # pixels came from, so the one field that can
                                             # always be filled in truthfully is the one
                                             # that can be required.
ADVISORY_SIDECAR_KEYS = ("model", "prompt", "generated_at")
KEY_COLOUR_KEYS = ("key", "key_rgb_requested", "key_rgb")
LONG_SIDE_RANGE = (2000, 2400)      # README's own guidance: a 4800px source renders
                                    # a supersampled warp four scenes deep, twice daily
REPLICATE_EXPORT_KEYS = ("input", "id", "status")   # present at top level only in a raw
                                                    # prediction export, never in our own
                                                    # template - the shape test
DEFAULT_MODEL = "google/nano-banana-pro"           # CLAUDE.md's default scene generator
                                                    # (2026-07-29) - what a prediction
                                                    # export never names, so it is the
                                                    # fallback, not a reading of the export
GEOMETRY_CARD_RE = re.compile(r"^geometry_card_(?P<group>.+)_[\d.]+\.png$")


def _fail(stage: str, msg: str) -> int:
    print(f"FAIL  stage {stage}: {msg}")
    return 1


def _validate_template_sidecar(sidecar: dict, sidecar_path: Path) -> dict | None:
    """Stage 0, our own _TEMPLATE.json shape. Returns None (having already
    printed why) rather than raising, so callers report a stage failure like
    every other stage instead of an uncaught exception."""
    missing = [k for k in REQUIRED_SIDECAR_KEYS if not sidecar.get(k)]
    if missing:
        _fail("0 sidecar", f"{sidecar_path.name} is missing required key(s): {', '.join(missing)}. "
              "Fill them in from _TEMPLATE.json before running intake.")
        return None
    if not any(sidecar.get(k) for k in KEY_COLOUR_KEYS):
        # Not a nag about a blank field: without a key colour there is no keyed
        # panel to extract, and `extract` would silently fall back to emerald and
        # key whatever happened to be greenish. A scene with no key is authored
        # through the seeded path, which this tool does not drive.
        _fail("0 sidecar", f"{sidecar_path.name} declares no key colour "
              f"({'/'.join(KEY_COLOUR_KEYS)} all absent or null). A keyed scene must name "
              "its key; a scene with no key at all (a photograph, like "
              "flat_leaning_bookstack) is authored with "
              "`scene_author.py extract ... --seeded`, which intake does not drive.")
        return None
    vague = [k for k in ADVISORY_SIDECAR_KEYS if not sidecar.get(k)]
    if vague:
        print(f"WARN  stage 0 sidecar: no {', '.join(vague)} recorded - carried into "
              "scene.json as null. Honest for a photograph or a pre-P4b scene; a gap in "
              "the provenance for anything generated from here on.")
    return sidecar


def _is_replicate_export(raw: dict) -> bool:
    return all(k in raw for k in REPLICATE_EXPORT_KEYS)


def _geometry_card_group(image_input) -> str | None:
    """The group a reference geometry card was authored for, parsed off its own
    filename (`geometry_card_<group>_<ratio>.png`) - the cards are painted in
    KEYS['emerald'] exactly (pivot doc §3.1), so finding one also answers the
    key colour. None if `image_input` names no recognisable card."""
    for url in image_input or []:
        m = GEOMETRY_CARD_RE.match(url.rsplit("/", 1)[-1])
        if m:
            return m["group"]
    return None


def _handle_replicate_export(raw: dict, image_path: Path, group_type: str,
                             model_override: str, key_override: str,
                             name_override: str, dry_run: bool, force: bool = False):
    """Stage 0, Replicate prediction shape: the owner's real hand-run artefact
    downloaded straight from the playground - id/status/input/urls/metrics at
    the top level, no model name anywhere and no `scene`/`tag`/`key_rgb` of
    our own template's either. Returns (provenance, scene, tag, image_path), or
    None having already printed why."""
    status, inp = raw.get("status"), raw.get("input") or {}
    if status != "succeeded" or not inp.get("prompt"):
        _fail("0 sidecar", f"prediction {raw.get('id', '?')} is not usable "
              f"(status={status!r}, has prompt={bool(inp.get('prompt'))}) - a failed or "
              "cancelled prediction must never be authored.")
        return None

    stem = image_path.stem
    if stem.startswith("replicate-prediction") and not name_override:
        _fail("0 sidecar", f"'{stem}' is a prediction id, not a scene name (inflow "
              "README wants <tag>_<descriptor>, tag drives gallery order) - "
              "re-run with --name <scene_name>.")
        return None
    scene = name_override or stem

    card_group = _geometry_card_group(inp.get("image_input"))
    if card_group is None:
        if not key_override:
            _fail("0 sidecar", "no geometry card recognised in input.image_input, so the "
                  "key colour can't be derived from it - pass --key emerald|magenta.")
            return None
        if key_override not in scene_generate.KEYS:
            _fail("0 sidecar", f"unknown --key {key_override!r}, must be one of "
                  f"{sorted(scene_generate.KEYS)}.")
            return None
        key_name = key_override
    else:
        if card_group != group_type and not force:
            _fail("0 sidecar", f"the attached geometry card is for group '{card_group}' but "
                  f"this image is in the '{group_type}' inflow folder - the scene was "
                  "generated at the wrong proportions and no amount of authoring fixes "
                  f"that; regenerate against geometry_card_{group_type}_*.png. "
                  "If the miss happens to land inside *this* group's printed range, "
                  "--force harvests it here and lets the screen decide.")
            return None
        if card_group != group_type:
            # A model that misses its card can still land squarely inside another
            # group's printed range - the 10x24 stairwell scene that rendered 0.7123
            # is a primary scene, not a wasted generation (§4's harvest, same logic).
            # The card only ever *suggested* the group; the screen's aspect check
            # measures the rectangle that actually rendered and still has to pass.
            print(f"WARN  stage 0 sidecar: geometry card is '{card_group}' but authoring as "
                  f"'{group_type}' (--force). The screen's aspect check decides, not the card.")
        key_name = "emerald"      # the card's own paint colour, not a guess (pivot doc §3.1)
    key_rgb = scene_generate.KEYS[key_name]["rgb"]

    provenance = dict(raw)        # carry the whole export unflattened - provenance is the point
    provenance.update({
        "prompt": inp["prompt"],
        "generated_at": raw.get("completed_at"),
        "generated_via": f"Replicate (manual), prediction {raw.get('id')}, "
                         f"{(raw.get('urls') or {}).get('web')}",
        "prediction_id": raw.get("id"),
        "model": model_override or DEFAULT_MODEL,
        "model_source": "given via --model" if model_override else
                        "the prediction export does not name the model; defaulted, not read",
        "key": key_name,
        "key_rgb": list(key_rgb),
    })
    tag = None  # resolved by the caller, same rule as the template shape

    if not dry_run and name_override:
        json_path = image_path.with_suffix(".json")
        new_png, new_json = image_path.with_name(f"{scene}.png"), image_path.with_name(f"{scene}.json")
        image_path.rename(new_png)
        json_path.rename(new_json)
        print(f"      renamed {image_path.name} + {json_path.name} -> "
              f"{new_png.name} + {new_json.name} (prediction id survives in scene.json)")
        image_path = new_png

    return provenance, scene, tag, image_path


def _check_source_size(image_path: Path) -> None:
    """Stage 1. WARN ONLY - the README's own range is a courtesy to the warp,
    not a gate; an owner who wants a bigger source for another reason can keep it."""
    w, h = Image.open(image_path).size
    long_side = max(w, h)
    lo, hi = LONG_SIDE_RANGE
    if not (lo <= long_side <= hi):
        print(f"WARN  stage 1 size: {w}x{h}, long side {long_side}px outside ~{lo}-{hi}px - "
              "a larger source renders a supersampled warp four scenes deep, twice daily, "
              "for no gallery benefit; a much smaller one leaves less print area than an "
              "Etsy gallery image needs.")


def _labelled_pair(bare: np.ndarray, comp: np.ndarray, out_path: Path) -> Path:
    """Bare scene beside the composite, labelled - review order is full-frame
    gestalt, then this pair, then corners, then edge strips; never crops alone."""
    b = Image.fromarray(bare.astype(np.uint8))
    c = Image.fromarray(comp.astype(np.uint8))
    pad, label_h = 8, 18
    w = b.width + pad + c.width
    h = max(b.height, c.height) + label_h
    out = Image.new("RGB", (w, h), (24, 24, 24))
    dr = ImageDraw.Draw(out)
    out.paste(b, (0, label_h))
    out.paste(c, (b.width + pad, label_h))
    dr.text((0, 0), "bare scene", (200, 200, 200))
    dr.text((b.width + pad, 0), "composite", (200, 200, 200))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path)
    return out_path


def _backup_bundle(bundle_dir: Path, passed: bool, screen_metrics: dict, gate_findings: list) -> None:
    """GL-30b: land this bundle in R2 as it is authored, with its verdict, so
    the GL-30 one-off sweep never has to be repeated for anything screened
    after it. Same write-once key discipline as corpus_backup.KEY_PREFIX. A
    backup problem is printed, never raised - intake has no row of its own to
    write a state change onto, so the printed line is that state change; it
    must never turn a passing scene into a failing one."""
    if not corpus_backup.config.is_r2_configured():
        print("SKIP  backup: R2 not configured (need all of: " +
              ", ".join(corpus_backup.config.R2_ENV_VARS) + ") - bundle stays local only")
        return
    verdict_path = bundle_dir / "verdict.json"
    verdict_path.write_text(json.dumps({
        "passed": passed, "screen_metrics": screen_metrics, "gate_findings": gate_findings,
    }, indent=2) + "\n", encoding="utf-8")
    paths = [(p.relative_to(ROOT).as_posix(), p) for p in sorted(bundle_dir.iterdir()) if p.is_file()]
    try:
        corpus_backup.back_up_paths(paths, manifest_path=corpus_backup.DEFAULT_MANIFEST, upload=True)
    except (SystemExit, Exception) as exc:         # noqa: BLE001 - see the docstring
        print(f"WARN  backup: {exc} - bundle stays local only")


def run(image_path: Path, dry_run: bool, group_override: str, orientation_override: str,
        model_override: str = None, key_override: str = None, name_override: str = None,
        tag_override: str = None, force: bool = False) -> int:
    sidecar_path = image_path.with_suffix(".json")
    if not sidecar_path.exists():
        return _fail("0 sidecar", f"no {sidecar_path.name} beside {image_path.name}. "
                     f"Copy assets/mockups/inflow/_TEMPLATE.json to {sidecar_path} and fill it "
                     "in (or drop the Replicate prediction export instead) before running "
                     "intake - there is no way to recover provenance after the fact.")
    raw = json.loads(sidecar_path.read_text())
    group_type = group_override or image_path.parent.name

    if _is_replicate_export(raw):
        result = _handle_replicate_export(raw, image_path, group_type, model_override,
                                          key_override, name_override, dry_run, force)
        if result is None:
            return 1
        provenance, scene, tag, image_path = result
        orientation = orientation_override or "portrait"   # the export carries no orientation
    else:
        sidecar = _validate_template_sidecar(raw, sidecar_path)
        if sidecar is None:
            return 1
        orientation = orientation_override or sidecar.get("orientation", "portrait")
        scene = sidecar.get("scene") or image_path.stem
        tag = sidecar.get("tag")
        provenance = scene_author.normalise_provenance(sidecar)
    tag = tag_override or tag or scene.split("_", 1)[0]
    key_rgb = tuple(provenance["key_rgb"])

    _check_source_size(image_path)

    screen_result = ss.screen(image_path, key_rgb, group_type)
    # The screen is a ranker; only `aspect` is a fact about the pixels that no
    # authoring can change, and only `aspect` is unforceable. Every other check is
    # stricter than the nine-detector gate that actually decides: plan §3.4's open
    # question 2 recorded `lifestyle_shelf_books` gating 8/8 while failing the
    # screen's `frontal` at 0.087, and said to make non-aspect failures overridable
    # rather than loosen the screen if it bit again. It bit twice more on 2026-07-31
    # (a reading nook at frontal 0.081, a sofa scene at area 0.074).
    if not screen_result["passed"]:
        forcible = "aspect" not in screen_result["fail"] and force
        head = "WARN " if forcible else "FAIL "
        print(f"{head} stage 2 screen: {screen_result['fail']} {screen_result['metrics']}")
        if "aspect" in screen_result["fail"]:
            print(f"  aspect cannot be fixed by authoring - regenerate this scene with "
                  f"assets/mockups/geometry_cards/geometry_card_{group_type}_*.png as a "
                  f"reference image. No bundle was written; re-authoring this PNG would "
                  f"only reach C3's cover-crop guard and be refused there too.")
            return 1
        if not forcible:
            print("  no bundle was written. Re-run with --force to author it anyway and let "
                  "the gate decide - the screen is a ranker, the gate is the gate.")
            return 1
        print("  forced past a non-aspect screen failure; the gate below is what decides. "
              "The failed check is still reported in the verdict block.")
    else:
        print(f"pass  stage 2 screen: {screen_result['metrics']}")

    rgb = np.asarray(Image.open(image_path).convert("RGB"))
    contam = ss.key_contamination(rgb, ss.key_model(rgb, key_rgb))
    if contam["protrusion"] or contam["intrusion"]:
        print(f"WARN  stage 3 key-collision: {contam['protrusion']}px protrusion, "
              f"{contam['intrusion']}px intrusion - a prop near the key colour may be "
              f"getting swallowed into the mask (CLAUDE.md: emerald and green foliage "
              f"don't mix; key that scene in magenta instead). clusters={contam['clusters']}")
    else:
        print("ok    stage 3 key-collision: none")

    out_root = ROOT / "outputs" / "scene_intake" / scene / "bundle" if dry_run else scene_author.MOCKUPS
    try:
        extracted = scene_author.extract(image_path, scene, tag, provenance,
                                         group_type=group_type, orientation=orientation,
                                         out_root=out_root)
    except SystemExit as e:
        return _fail("4 extract", str(e))
    bundle_dir = Path(extracted["dir"])
    print(f"ok    stage 4 extract: {bundle_dir}")

    art = Image.open(mockup_qa.MASTER).convert("RGB")
    gate = mockup_qa.check(bundle_dir, art)

    art_dir = ROOT / "outputs" / "scene_intake" / scene
    sheet = mockup_qa.contact_sheet(gate, art_dir / "contact_sheet.png")
    pair = _labelled_pair(gate["parts"]["bare"], gate["parts"]["comp"],
                          art_dir / "bare_vs_composite.png")
    print(f"      artifacts: {sheet}, {pair}")

    print(f"\n{'=' * 70}\nVERDICT {scene}\n{'=' * 70}")
    m = screen_result["metrics"]
    fails = set(screen_result["fail"])
    for name, val, limit, fail_key in (
        ("area", m["area"], f"in [{ss.AREA_RANGE[0]}, {ss.AREA_RANGE[1]}]", "area"),
        ("single", m["components"], "== 1", "single"),
        ("solidity", m["solidity"], f">= {ss.SOLIDITY_MIN}", "solidity"),
        ("aspect", m["aspect"], f"gap <= {ss.ASPECT_TOL}", "aspect"),
        ("occluders", m["occluders"], f"<= {ss.OCCLUDER_MAX}", "occluders"),
        ("sharp", m["sharp"], f"<= {ss.SHARP_MAX}", "sharp"),
        ("outside", m["outside"], f"<= {ss.OUTSIDE_MAX}", "no-outside"),
        ("frontal", m["frontal"], f"<= {ss.FRONTAL_TOL}", "frontal"),
        ("nested", m["nested"], f"<= {ss.NESTED_MAX}", "no-nested"),
    ):
        ok = fail_key not in fails
        print(f"  {'ok  ' if ok else 'FAIL'} screen {name:12} {val!s:10} {limit}")
    print(f"  {'WARN' if contam['protrusion'] or contam['intrusion'] else 'ok  '} "
          f"collision protrusion={contam['protrusion']}px intrusion={contam['intrusion']}px")
    for f in gate["findings"]:
        mark = "WAIV" if f.get("waived") else ("ok  " if f["passed"] else "FAIL")
        print(f"  {mark} gate   {f['name']:20} {f['detail']}")

    passed = (screen_result["passed"] or force) and gate["passed"]
    print(f"{'=' * 70}\n{'PASS' if passed else 'FAIL'} overall"
          f"{' (screen forced)' if passed and not screen_result['passed'] else ''}"
          f" - bundle at {bundle_dir}")
    if not passed:
        print("bundle kept on disk for inspection; fix the failing detector(s) above, "
              "or re-author, before this scene goes to the owner.")

    if not dry_run:
        _backup_bundle(bundle_dir, passed, screen_result["metrics"], gate["findings"])

    return 0 if passed else 1


def main(argv):
    if len(argv) < 2 or argv[1].startswith("--"):
        raise SystemExit(__doc__)
    image_path = Path(argv[1])
    if not image_path.exists():
        raise SystemExit(_fail("0 image", f"no such image: {image_path}"))
    dry_run = "--dry-run" in argv
    group_override = argv[argv.index("--group") + 1] if "--group" in argv else None
    orientation_override = argv[argv.index("--orientation") + 1] if "--orientation" in argv else None
    model_override = argv[argv.index("--model") + 1] if "--model" in argv else None
    key_override = argv[argv.index("--key") + 1] if "--key" in argv else None
    name_override = argv[argv.index("--name") + 1] if "--name" in argv else None
    tag_override = argv[argv.index("--tag") + 1] if "--tag" in argv else None
    force = "--force" in argv
    return run(image_path, dry_run, group_override, orientation_override,
              model_override, key_override, name_override, tag_override, force)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
