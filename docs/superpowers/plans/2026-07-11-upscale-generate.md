# Upscale-in-generate.py Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `candidates.base_image_url` always hold an upscaled, 300-DPI-capable master image instead of FLUX schnell's raw ~1MP output, so `primary_mockup.py`'s Gelato `create_product_from_template` call (which enforces a 300 DPI floor) stops receiving an image that's 1-2 orders of magnitude too small.

**Architecture:** Extend `pipeline/replicate_client.py` with a shared `_predict()` helper used by both the existing `generate_image()` (now requesting `aspect_ratio="2:3"`/`megapixels="1"` instead of undocumented defaults) and a new `upscale_image()` (calls `nightmareai/real-esrgan`, a pure super-resolution model, `scale=4`). `pipeline/generate.py`'s `generate_for_candidate()` chains both calls and writes one combined row update. No new pipeline stage, no new cron function, no change to `critic_pass.py` or `primary_mockup.py`.

**Tech Stack:** Python 3, `urllib`/`sqlite3` (stdlib), `pytest` + `unittest.mock` — same conventions as the rest of `pipeline/`.

## Global Constraints

Per the approved design (`docs/superpowers/specs/2026-07-11-upscale-generate-design.md`):

- **No new pipeline stage.** This is entirely inside the existing `generate` stage (2 of 12). CLAUDE.md's 12-stage list is unchanged.
- **`generate_for_candidate` keeps its all-or-nothing write.** If `upscale_image` raises, no `UPDATE` happens — the candidate row is left exactly as it was, so the existing per-candidate try/except in `run_generate_cycle` and in `critic_pass.run_critic_pass`'s retry loop retries it next cycle unchanged. Neither of those two callers is modified by this plan.
- **A single `scale=4` real-esrgan pass covers the 8x12 primary size (needs ~2400x3600px/~8.6MP at 300 DPI) and closely covers A3 (~3507x4961px/~17.4MP).** It does **not** yet cover A2, A1, or the 10x24 group (all need more linear scale — a second chained pass or a higher-capacity model). Per CLAUDE.md's own staged rollout ("Before the first real M1 manual run: at minimum, the 8x12″ (primary) templates must be real. Before the M1 multi-size fan-out test: at minimum, one secondary size's templates must also be real."), this is sufficient for the primary-only M1 milestone this plan targets. Reaching A2/A1/10x24 is flagged, not built here.
- **No pinned Replicate model version.** Both `generate_image` and `upscale_image` hit `models/{owner}/{name}/predictions` (the "always latest version" shorthand), matching the existing `FLUX_SCHNELL_MODEL` convention — never a version-pinned URL.
- Every stage module in this pipeline gets its own commit per passing test group, per CLAUDE.md's "commit after each stage passes its manual M1 test."

---

## Task 1: `generate_image()` requests portrait aspect ratio and max megapixels

**Files:**
- Modify: `pipeline/replicate_client.py:16-42`
- Modify: `tests/test_replicate_client.py:9-31`

**Interfaces:**
- `generate_image(prompt: str, *, api_token: str = None) -> dict` — signature unchanged, only its request body changes. Still consumed by `pipeline/generate.py`'s `generate_for_candidate` exactly as before.

- [ ] **Step 1: Update the failing test**

Replace `test_generate_image_builds_correct_request_and_parses_response` in `tests/test_replicate_client.py` with:

```python
def test_generate_image_builds_correct_request_and_parses_response():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["auth_header"] = request.get_header("Authorization")
        captured["prefer_header"] = request.get_header("Prefer")
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return {"id": "pred123", "status": "succeeded", "output": ["https://replicate.delivery/out.png"]}

    with patch("pipeline.replicate_client.http.send", side_effect=fake_send):
        result = replicate_client.generate_image("a botanical watercolor poster", api_token="test-token")

    assert captured["url"] == "https://api.replicate.com/v1/models/black-forest-labs/flux-schnell/predictions"
    assert captured["auth_header"] == "Bearer test-token"
    assert captured["prefer_header"] == "wait"
    assert captured["body"]["input"]["prompt"] == "a botanical watercolor poster"
    # Portrait primary template is 8x12 (2:3) - FLUX schnell defaults to square 1:1 and
    # ~1MP unless told otherwise; megapixels="1" is schnell's max native resolution.
    assert captured["body"]["input"]["aspect_ratio"] == "2:3"
    assert captured["body"]["input"]["megapixels"] == "1"
    assert result == {"image_url": "https://replicate.delivery/out.png", "prediction_id": "pred123"}
    # Replicate's Prefer: wait can hold the connection open up to 60s server-side;
    # the client-side socket timeout must be at least that long or the raw
    # URLError/socket timeout fires before our ReplicatePredictionTimeoutError can.
    assert captured["timeout"] >= 60
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_replicate_client.py::test_generate_image_builds_correct_request_and_parses_response -v`
Expected: FAIL — `KeyError: 'aspect_ratio'` (the current request body doesn't include it).

- [ ] **Step 3: Implement**

In `pipeline/replicate_client.py`, replace the body-building line inside `generate_image`:

```python
    body = json.dumps({"input": {"prompt": prompt}}).encode("utf-8")
```

with:

```python
    body = json.dumps({
        "input": {"prompt": prompt, "aspect_ratio": "2:3", "megapixels": "1"}
    }).encode("utf-8")
```

- [ ] **Step 4: Run the full replicate_client test file to verify everything passes**

Run: `python -m pytest tests/test_replicate_client.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/replicate_client.py tests/test_replicate_client.py
git commit -m "fix: request portrait aspect ratio and max megapixels from FLUX schnell"
```

---

## Task 2: `upscale_image()` via a shared `_predict()` helper

**Files:**
- Modify: `pipeline/replicate_client.py`
- Modify: `tests/test_replicate_client.py`

**Interfaces:**
- Produces: `upscale_image(image_url: str, *, api_token: str = None) -> dict` returning `{"image_url": str, "prediction_id": str}` — same shape as `generate_image`'s return. Consumed by Task 3's `generate_for_candidate`.
- Internal only (not consumed outside this file): `_predict(model: str, input_body: dict, *, api_token: str) -> dict` — both `generate_image` and `upscale_image` call this; not tested directly, only through its two callers.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_replicate_client.py`:

```python
def test_upscale_image_builds_correct_request_and_parses_response():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["auth_header"] = request.get_header("Authorization")
        captured["prefer_header"] = request.get_header("Prefer")
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return {"id": "pred-up1", "status": "succeeded", "output": ["https://replicate.delivery/upscaled.png"]}

    with patch("pipeline.replicate_client.http.send", side_effect=fake_send):
        result = replicate_client.upscale_image("https://replicate.delivery/out.png", api_token="test-token")

    assert captured["url"] == "https://api.replicate.com/v1/models/nightmareai/real-esrgan/predictions"
    assert captured["auth_header"] == "Bearer test-token"
    assert captured["prefer_header"] == "wait"
    assert captured["body"]["input"] == {
        "image": "https://replicate.delivery/out.png",
        "scale": 4,
        "face_enhance": False,
    }
    assert result == {"image_url": "https://replicate.delivery/upscaled.png", "prediction_id": "pred-up1"}
    assert captured["timeout"] >= 60


def test_upscale_image_raises_timeout_error_when_not_succeeded():
    def fake_send(request, timeout=30):
        return {"id": "pred-up2", "status": "processing", "output": None}

    with patch("pipeline.replicate_client.http.send", side_effect=fake_send):
        with pytest.raises(replicate_client.ReplicatePredictionTimeoutError, match="pred-up2"):
            replicate_client.upscale_image("https://replicate.delivery/out.png", api_token="test-token")


def test_upscale_image_api_token_defaults_to_env_var(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "env-token")
    captured = {}

    def fake_send(request, timeout=30):
        captured["auth_header"] = request.get_header("Authorization")
        return {"id": "pred-up3", "status": "succeeded", "output": ["https://replicate.delivery/upscaled2.png"]}

    with patch("pipeline.replicate_client.http.send", side_effect=fake_send):
        replicate_client.upscale_image("https://replicate.delivery/out.png")

    assert captured["auth_header"] == "Bearer env-token"
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python -m pytest tests/test_replicate_client.py -v`
Expected: the 3 new tests FAIL with `AttributeError: module 'pipeline.replicate_client' has no attribute 'upscale_image'`.

- [ ] **Step 3: Implement**

Replace the entire body of `pipeline/replicate_client.py` from `generate_image` onward (i.e. everything after the `ReplicatePredictionTimeoutError` class) with:

```python
UPSCALE_MODEL = "nightmareai/real-esrgan"  # pure super-resolution GAN, no diffusion/hallucinated
# content - safer for compliance than a diffusion-based upscaler. A single scale=4 pass covers
# the 8x12 primary size and A3 at 300 DPI; A2/A1/10x24 need more linear scale (see plan notes).


def _predict(model: str, input_body: dict, *, api_token: str) -> dict:
    url = f"{REPLICATE_API_BASE}/{model}/predictions"
    body = json.dumps({"input": input_body}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_token}",
            "Prefer": "wait",
        },
        method="POST",
    )
    result = http.send(request, timeout=65)

    if result.get("status") != "succeeded":
        raise ReplicatePredictionTimeoutError(
            f"Replicate prediction {result.get('id')} on {model} did not complete within "
            f"the 60s synchronous wait window (status: {result.get('status')}). This likely "
            f"indicates a Replicate-side outage or throttling, not a pipeline bug."
        )

    output = result["output"]
    image_url = output[0] if isinstance(output, list) else output
    return {"image_url": image_url, "prediction_id": result["id"]}


def generate_image(prompt: str, *, api_token: str = None) -> dict:
    api_token = api_token or config.require_env("REPLICATE_API_TOKEN")
    return _predict(
        FLUX_SCHNELL_MODEL,
        {"prompt": prompt, "aspect_ratio": "2:3", "megapixels": "1"},
        api_token=api_token,
    )


def upscale_image(image_url: str, *, api_token: str = None) -> dict:
    api_token = api_token or config.require_env("REPLICATE_API_TOKEN")
    return _predict(
        UPSCALE_MODEL,
        {"image": image_url, "scale": 4, "face_enhance": False},
        api_token=api_token,
    )
```

- [ ] **Step 4: Run the full replicate_client test file to verify everything passes**

Run: `python -m pytest tests/test_replicate_client.py -v`
Expected: all 6 tests PASS (the original 3, now routed through `_predict`, plus the 3 new ones).

- [ ] **Step 5: Commit**

```bash
git add pipeline/replicate_client.py tests/test_replicate_client.py
git commit -m "feat: add replicate_client.py upscale_image via shared _predict helper"
```

---

## Task 3: Wire `upscale_image` into `generate_for_candidate`

**Files:**
- Modify: `db/schema.sql:1-17`
- Modify: `pipeline/generate.py:28-50`
- Modify: `tests/test_generate.py`
- Modify: `tests/test_critic_pass.py:376-489` (two tests call the *real* `generate_for_candidate`
  through `run_critic_pass`'s retry loop and only mock `replicate_client.generate_image` -
  confirmed by reading the file. Once `generate_for_candidate` also calls `upscale_image`, both
  tests would fall through to a real, unmocked network call unless `upscale_image` is mocked too.)

**Interfaces:**
- `generate_for_candidate(conn, candidate_id: int, *, correction_note: str = None, api_token: str = None, now=None) -> dict` — signature unchanged. Return value now includes an extra key: `{"image_url": str, "prediction_id": str, "upscale_prediction_id": str}` (`image_url` is now the **upscaled** URL, `prediction_id` is still the FLUX prediction id). Callers of the return value: only tests currently (`critic_pass.py`'s retry loop calls this function but ignores its return value - confirmed at `pipeline/critic_pass.py:177-180` - so this is not a breaking change for it).
- Consumes: `replicate_client.generate_image` and `replicate_client.upscale_image` from Task 1/2, both patched independently in tests via `pipeline.generate.replicate_client.generate_image` / `pipeline.generate.replicate_client.upscale_image`.

- [ ] **Step 1: Add the schema column**

In `db/schema.sql`, in the `candidates` table, add one line after `base_replicate_prediction_id TEXT,`:

```sql
CREATE TABLE IF NOT EXISTS candidates (
  id INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL,
  niche TEXT NOT NULL,
  style_theme_tags TEXT,
  trend_source TEXT,
  go_hold_kill TEXT NOT NULL CHECK(go_hold_kill IN ('go','hold','kill')),
  hold_recheck_date TEXT,
  kill_reason TEXT,
  base_image_url TEXT,
  base_replicate_prediction_id TEXT,
  base_upscale_prediction_id TEXT,
  status TEXT NOT NULL CHECK(status IN (
    'pending','generating','primary_review','compliance_failed','failed','abandoned','completed'
  )),
  failed_reason TEXT,
  updated_at TEXT NOT NULL
);
```

No migration needed - there's no persisted real database file yet (`db.init_db` applies this file fresh via `executescript`, and every test builds a throwaway `tmp_path` database from it).

- [ ] **Step 2: Update the failing tests**

Replace `test_generate_for_candidate_calls_replicate_and_writes_image_back` in `tests/test_generate.py` with:

```python
def test_generate_for_candidate_calls_replicate_and_writes_image_back(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_pending_candidate(conn, niche="monstera line art")
    captured = {}

    def fake_generate_image(prompt, *, api_token=None):
        captured["prompt"] = prompt
        captured["api_token"] = api_token
        return {"image_url": "https://replicate.delivery/raw.png", "prediction_id": "pred123"}

    def fake_upscale_image(image_url, *, api_token=None):
        captured["upscale_input_url"] = image_url
        return {"image_url": "https://replicate.delivery/upscaled.png", "prediction_id": "pred-up1"}

    with patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image), \
         patch("pipeline.generate.replicate_client.upscale_image", side_effect=fake_upscale_image):
        result = generate.generate_for_candidate(
            conn, candidate_id, api_token="test-token", now=datetime(2026, 7, 9, 10, 0, 0)
        )

    assert result == {
        "image_url": "https://replicate.delivery/upscaled.png",
        "prediction_id": "pred123",
        "upscale_prediction_id": "pred-up1",
    }
    assert "monstera line art" in captured["prompt"]
    assert captured["api_token"] == "test-token"
    assert captured["upscale_input_url"] == "https://replicate.delivery/raw.png"

    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert row["base_image_url"] == "https://replicate.delivery/upscaled.png"
    assert row["base_replicate_prediction_id"] == "pred123"
    assert row["base_upscale_prediction_id"] == "pred-up1"
    assert row["status"] == "generating"
    assert row["updated_at"] == "2026-07-09T10:00:00"
    conn.close()
```

Replace `test_generate_for_candidate_passes_correction_note_into_prompt` with:

```python
def test_generate_for_candidate_passes_correction_note_into_prompt(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_pending_candidate(conn, niche="moon phase print", status="generating")
    captured = {}

    def fake_generate_image(prompt, *, api_token=None):
        captured["prompt"] = prompt
        return {"image_url": "https://replicate.delivery/retry.png", "prediction_id": "pred456"}

    def fake_upscale_image(image_url, *, api_token=None):
        return {"image_url": "https://replicate.delivery/retry-upscaled.png", "prediction_id": "pred-up2"}

    with patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image), \
         patch("pipeline.generate.replicate_client.upscale_image", side_effect=fake_upscale_image):
        generate.generate_for_candidate(
            conn, candidate_id, correction_note="composition was off-center",
            now=datetime(2026, 7, 9, 11, 0, 0),
        )

    assert "Previous attempt was rejected for: composition was off-center" in captured["prompt"]

    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert row["base_image_url"] == "https://replicate.delivery/retry-upscaled.png"
    conn.close()
```

Add a new test right after it:

```python
def test_generate_for_candidate_leaves_row_untouched_when_upscale_fails(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_pending_candidate(conn, niche="monstera line art", status="pending")

    def fake_generate_image(prompt, *, api_token=None):
        return {"image_url": "https://replicate.delivery/raw.png", "prediction_id": "pred-raw"}

    def fake_upscale_image(image_url, *, api_token=None):
        raise RuntimeError("Replicate upscale throttled")

    with patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image), \
         patch("pipeline.generate.replicate_client.upscale_image", side_effect=fake_upscale_image):
        with pytest.raises(RuntimeError, match="Replicate upscale throttled"):
            generate.generate_for_candidate(conn, candidate_id, api_token="test-token")

    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert row["status"] == "pending"
    assert row["base_image_url"] is None
    assert row["base_replicate_prediction_id"] is None
    assert row["base_upscale_prediction_id"] is None
    conn.close()
```

Replace `test_run_generate_cycle_processes_all_pending_candidates_and_skips_others` with:

```python
def test_run_generate_cycle_processes_all_pending_candidates_and_skips_others(tmp_path):
    conn = _fresh_conn(tmp_path)
    pending_id_1 = _insert_pending_candidate(conn, niche="monstera line art", status="pending")
    pending_id_2 = _insert_pending_candidate(conn, niche="moon phase print", status="pending")
    abandoned_id = _insert_pending_candidate(conn, niche="saturated term", status="abandoned")

    call_count = {"n": 0}

    def fake_generate_image(prompt, *, api_token=None):
        call_count["n"] += 1
        return {"image_url": f"https://replicate.delivery/out{call_count['n']}.png", "prediction_id": f"pred{call_count['n']}"}

    def fake_upscale_image(image_url, *, api_token=None):
        return {"image_url": image_url.replace("out", "upscaled"), "prediction_id": "pred-up"}

    with patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image), \
         patch("pipeline.generate.replicate_client.upscale_image", side_effect=fake_upscale_image):
        processed_ids = generate.run_generate_cycle(conn, now=datetime(2026, 7, 9, 12, 0, 0))

    assert sorted(processed_ids) == sorted([pending_id_1, pending_id_2])
    assert call_count["n"] == 2

    row_1 = conn.execute("SELECT * FROM candidates WHERE id = ?", (pending_id_1,)).fetchone()
    row_2 = conn.execute("SELECT * FROM candidates WHERE id = ?", (pending_id_2,)).fetchone()
    abandoned_row = conn.execute("SELECT * FROM candidates WHERE id = ?", (abandoned_id,)).fetchone()

    assert row_1["status"] == "generating"
    assert row_1["base_image_url"] is not None
    assert row_2["status"] == "generating"
    assert row_2["base_image_url"] is not None
    assert abandoned_row["status"] == "abandoned"
    assert abandoned_row["base_image_url"] is None
    conn.close()
```

Replace `test_run_generate_cycle_isolates_per_candidate_failures` with:

```python
def test_run_generate_cycle_isolates_per_candidate_failures(tmp_path):
    conn = _fresh_conn(tmp_path)
    failing_id = _insert_pending_candidate(conn, niche="monstera line art", status="pending")
    succeeding_id = _insert_pending_candidate(conn, niche="moon phase print", status="pending")

    def fake_generate_image(prompt, *, api_token=None):
        if "monstera line art" in prompt:
            raise RuntimeError("Replicate throttled")
        return {"image_url": "https://replicate.delivery/out2.png", "prediction_id": "pred2"}

    def fake_upscale_image(image_url, *, api_token=None):
        return {"image_url": "https://replicate.delivery/upscaled2.png", "prediction_id": "pred-up2"}

    with patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image), \
         patch("pipeline.generate.replicate_client.upscale_image", side_effect=fake_upscale_image):
        processed_ids = generate.run_generate_cycle(conn, now=datetime(2026, 7, 9, 12, 0, 0))

    assert processed_ids == [succeeding_id]

    failing_row = conn.execute("SELECT * FROM candidates WHERE id = ?", (failing_id,)).fetchone()
    succeeding_row = conn.execute("SELECT * FROM candidates WHERE id = ?", (succeeding_id,)).fetchone()

    assert failing_row["status"] == "pending"
    assert failing_row["base_image_url"] is None

    assert succeeding_row["status"] == "generating"
    assert succeeding_row["base_image_url"] == "https://replicate.delivery/upscaled2.png"
    conn.close()
```

`test_generate_for_candidate_raises_on_unknown_candidate_id` and `test_run_generate_cycle_returns_empty_list_when_no_pending_candidates` need no changes - neither exercises a Replicate call.

- [ ] **Step 3: Update `tests/test_critic_pass.py`'s two retry-path tests to also mock `upscale_image`**

These two tests call `critic_pass.run_critic_pass`, whose retry loop calls the *real*
`generate.generate_for_candidate` (not a mock of it) - they only patch
`pipeline.generate.replicate_client.generate_image`. Add a matching `upscale_image` fake and
patch, in both tests, so the retry path doesn't fall through to a real network call.

In `test_run_critic_pass_retries_once_then_passes`, add right after `fake_generate_image`:

```python
    def fake_upscale_image(image_url, *, api_token=None):
        return {"image_url": "https://replicate.delivery/retry-upscaled.png", "prediction_id": "pred_retry_up"}
```

and add `patch("pipeline.generate.replicate_client.upscale_image", side_effect=fake_upscale_image), \`
as a new line in the `with` block, immediately after the existing
`patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image), \` line.

Make the identical two additions (same `fake_upscale_image` body) in
`test_run_critic_pass_abandons_after_three_failures_and_triggers_fallback`.

Neither test asserts on `base_image_url` or the upscale prediction id, so no other assertion in
either test needs to change - this is purely to keep the retry path from making a real network
call.

- [ ] **Step 4: Run tests to verify the new/updated ones fail**

Run: `python -m pytest tests/test_generate.py tests/test_critic_pass.py -v`
Expected: FAIL - `tests/test_generate.py` fails with `sqlite3.OperationalError: table candidates
has no column named base_upscale_prediction_id` (schema not wired to `generate_for_candidate`
yet) or assertion mismatches on `base_image_url`/`result`. `tests/test_critic_pass.py`'s two
retry-path tests currently pass as-is (nothing to make fail yet) - they're being updated
pre-emptively so they don't break in Step 6; confirm they still pass at this point.

- [ ] **Step 5: Implement**

Replace `generate_for_candidate` in `pipeline/generate.py`:

```python
def generate_for_candidate(conn, candidate_id: int, *, correction_note: str = None,
                            api_token: str = None, now=None) -> dict:
    """Generate a base image for a candidate, then upscale it to a 300-DPI-capable master.
    Always overwrites base_image_url/base_replicate_prediction_id/base_upscale_prediction_id
    on its row (even on retry). If upscaling fails, no write happens - the row is left exactly
    as it was, so the caller's existing per-candidate retry handling picks it up again unchanged.
    `now` is only for test determinism."""
    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if row is None:
        raise ValueError(f"No candidate with id {candidate_id}")

    prompt = build_prompt(dict(row), correction_note=correction_note)
    generated = replicate_client.generate_image(prompt, api_token=api_token)
    upscaled = replicate_client.upscale_image(generated["image_url"], api_token=api_token)

    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    conn.execute(
        """
        UPDATE candidates
        SET base_image_url = ?, base_replicate_prediction_id = ?,
            base_upscale_prediction_id = ?, status = 'generating', updated_at = ?
        WHERE id = ?
        """,
        (upscaled["image_url"], generated["prediction_id"], upscaled["prediction_id"], timestamp, candidate_id),
    )
    conn.commit()
    return {
        "image_url": upscaled["image_url"],
        "prediction_id": generated["prediction_id"],
        "upscale_prediction_id": upscaled["prediction_id"],
    }
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_generate.py tests/test_critic_pass.py -v`
Expected: all 9 tests in `test_generate.py` PASS, and both updated retry-path tests in
`test_critic_pass.py` still PASS.

- [ ] **Step 7: Run the full test suite to confirm nothing else broke**

Run: `python -m pytest -v`
Expected: all PASS (db, config, http, gelato, replicate, telegram, etsy, anthropic, research,
generate, primary_mockup, compliance_draft, critic_pass, digest suites).

- [ ] **Step 8: Commit**

```bash
git add db/schema.sql pipeline/generate.py tests/test_generate.py tests/test_critic_pass.py
git commit -m "feat: wire upscale_image into generate_for_candidate before mockup creation"
```

---

## Self-Review Notes

- **Spec coverage:** `generate_image`'s `aspect_ratio`/`megapixels` fix (Task 1), the new `upscale_image` function reusing a shared `_predict` helper (Task 2), the combined-write/all-or-nothing error handling and new `base_upscale_prediction_id` column (Task 3) are all covered, matching `docs/superpowers/specs/2026-07-11-upscale-generate-design.md` sections 1-4. The "Deferred" section (no pre-filter gating) and "Non-goals" (no new stage, no orientation system, no pinned model version, no changes to `critic_pass.py`/`primary_mockup.py`) are honored by omission - no task touches those files or adds that logic.
- **Placeholder scan:** no TBD/"add error handling"/"similar to Task N" language. Every step has concrete, runnable code, including the exact `scale=4`/`face_enhance=False` real-esrgan input body (verified against Replicate's public docs/search results during planning, not guessed from training data alone).
- **Type consistency:** `_predict(model: str, input_body: dict, *, api_token: str) -> dict` (Task 2) returns the same `{"image_url", "prediction_id"}` shape both `generate_image` and `upscale_image` already return today, so `generate_for_candidate` (Task 3) can treat both call results identically. `generate_for_candidate`'s new return key `upscale_prediction_id` doesn't collide with anything - confirmed its only real caller (`critic_pass.py:177-180`) discards the return value entirely.
- **Caught during self-review:** the initial draft of this plan assumed `test_critic_pass.py` mocked `generate_for_candidate` itself and needed no changes. Rereading the file (`tests/test_critic_pass.py:376-489`) showed two tests instead call the *real* `generate_for_candidate` through `run_critic_pass`'s retry loop, patching only `replicate_client.generate_image` - so they'd have hit a real network call once `upscale_image` was added. Fixed by adding Task 3 Step 3, patching `upscale_image` in both tests.
