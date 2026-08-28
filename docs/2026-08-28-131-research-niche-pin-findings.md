# GL-131: Research phase never proven to research anything beyond the botanical/evergreen-nature bucket

## Verdict

(b) The pin is `collect_event_lookahead()` (`pipeline/research.py:131-143`), which hardcodes the
literal substring `"botanical/minimalist nature illustration - "` into every one of its six niches
— 100% of that source is botanical by construction, no LLM or scoring step involved. A second,
softer mechanism compounds it: `TRENDING_NOW_PROMPT` (`pipeline/research.py:180-187`) steers its
web-search LLM call toward "botanical/minimalist wall art" and "nature, botanical, minimalist
landscape wall art" — the live census shows this does not hard-pin the LLM's output (it returns
mountain/landscape/japandi/mid-century-adjacent phrasing event_lookahead never would), but every
one of 121 observed rows still stayed inside the nature/landscape/earth-tone semantic neighborhood.
Neither mechanism is why the bucket has *only ever* been observed as botanical, though: the
`safe_evergreen_fallback` path is the one source in the codebase that can genuinely produce
celestial, mid-century, animal, map, or Japanese-art niches (`docs/safe_evergreen_bucket.md`
`## Buckets`), and the census shows it has fired **zero times** in the DB's full history. It has
never had the chance to diversify anything.

## Candidate census

Query run against the live, production `db/qhoto.sqlite3` (opened read-only via
`file:...?mode=ro`, no writes):

```sql
SELECT trend_source, niche, go_hold_kill, status, created_at FROM candidates ORDER BY created_at;
```

- **Total candidates:** 219

Per-`trend_source`-prefix breakdown (the four automatic/on-demand sources named in the issue):

| prefix | count |
| --- | --- |
| `event_lookahead:` | 64 |
| `trending_now:` | 121 |
| `safe_evergreen_fallback:` | 0 |
| `telegram_on_demand:` | 0 |
| other (`manual_live_test`, `s4_validation:*` — test/manual rows, not one of the four automatic sources) | 34 |

Non-botanical-literal check within the four automatic prefixes: every `event_lookahead:` niche
contains `"botanical"` (64/64, guaranteed by the f-string). Within `trending_now:` (121 rows, 63
distinct niches), 69/121 contain the literal substring `"botanical"`; broadening the match to
`{botanical, nature, leaf, flower, fern, moss, branch, landscape, mountain, biophilic, sage,
japandi, foliage, earth tone}` covers 121/121 — every single `trending_now` row observed to date
stays inside that neighborhood. Distinct phrasing does surface (`minimalist mountain landscape
poster`, `japandi minimalist line art print`, `moss wall art`, `boho mountain landscape wall art`)
— genuinely different from `collect_event_lookahead`'s fixed string — but none of it is celestial,
mid-century, animal, map, or Japanese-art in the sense `docs/safe_evergreen_bucket.md`'s `##
Buckets` uses those words. `safe_evergreen_fallback:` and `telegram_on_demand:` both show 0 — the
former never fired, the latter was never invoked in this DB's history.

## Mechanisms

- **`collect_event_lookahead()` — `pipeline/research.py:131-143`. RULED IN (hard pin).** The niche
  for every one of the six `EVENT_WINDOWS_2026` entries is
  `f"botanical/minimalist nature illustration - {window['name']}"` — the event name is the only
  variable part; the niche prefix is a fixed literal. 64/64 observed rows from this source contain
  `"botanical"`, matching the code exactly with no exceptions possible.
- **`pick_safe_evergreen_fallback()` — `pipeline/research.py:57-68`. RULED OUT as a pin, but named
  as the actual finding.** The function itself is unbiased: it reads `FALLBACK_CLASSES = ("subject",
  "style")` (`:54`) from `docs/safe_evergreen_bucket.md`, whose `## Buckets` section holds celestial,
  mid-century, landscape, animal, map, and Japanese-art seeds alongside the botanical ones, and
  picks uniformly via `rng.choice`. Nothing in this function favors botanical. The reason it has
  never produced a non-botanical candidate is that it has never run: `run_research_cycle`
  (`:337`) only calls it when `not any_go and auto_sources`, and `collect_event_lookahead()` alone
  supplies a `go` in most windows (`_classify_by_timing`, `:163`), so `any_go` is set before the
  fallback check is reached. The starvation condition this fallback exists for essentially never
  occurs while `EVENT_WINDOWS_2026` covers 6 of the year's windows.
- **`TRENDING_NOW_PROMPT` — `pipeline/research.py:180-187`. RULED IN (soft steer, not a hard pin).**
  The prompt text itself says "a shop selling AI-generated botanical/minimalist wall art" and
  "fit this niche (nature, botanical, minimalist landscape wall art)" — an explicit steer written
  into the instructions the web-search LLM call receives. The census shows this steer is not
  absolute (the LLM does return non-literally-botanical phrasing such as `mountain landscape`,
  `japandi`, `moss`), but of 121 observed rows, 0 left the broader nature/landscape/earth-tone
  neighborhood the prompt names. The prompt is doing real work, just not deterministic work.
- **Demand-ratio scoring path — `_classify_by_demand()` `pipeline/research.py:190-200`,
  `KILL_DEMAND_RATIO_THRESHOLD` `:178`. RULED OUT.** This path only ever runs after a keyword
  already exists (it classifies a candidate's `demand_ratio` as `go` or `kill`); it has no branch
  that can generate, substitute, or bias toward a keyword. It can only remove trending_now
  candidates whose Etsy demand is too thin, which is orthogonal to which niche family they came
  from. Not a plausible pinning mechanism, confirmed by reading the call path — `classify()`
  (`:146`) routes to `_classify_by_demand` only when `raw["demand_ratio"] is not None`, and that
  field is populated by `_build_demand_checked_candidate` from an already-decided `keyword`
  (`:203-225`).

## What would have to change

- To let `event_lookahead` diversify: replace the fixed
  `"botanical/minimalist nature illustration - {window['name']}"` literal with a niche selected
  per-window (e.g. from `docs/safe_evergreen_bucket.md`'s non-botanical buckets), so the six event
  windows aren't structurally all-botanical.
- To let the fallback actually get exercised: either loosen `any_go`'s definition so
  `collect_event_lookahead()` alone doesn't always satisfy it, or give the fallback its own
  cadence independent of `auto_sources`/`any_go` gating, so the celestial/mid-century/animal/map/
  Japanese seeds in `docs/safe_evergreen_bucket.md` get a real chance to surface.
- To loosen `trending_now`'s steer: rewrite `TRENDING_NOW_PROMPT` to stop naming
  "botanical"/"nature"/"minimalist landscape" as the niche and instead ask for wall-art niches
  broadly, letting the LLM's own web search surface whatever is actually trending.

This sortie makes no change to any of the above — it is #132/#133's business.

## Handoff

#132 and #133 both depend on this row's verdict: the fix each needs is not "improve the scoring",
it's making `collect_event_lookahead()`'s niche non-fixed and giving `pick_safe_evergreen_fallback()`
a real chance to fire, since the demand-ratio path was ruled out as a lever entirely.
