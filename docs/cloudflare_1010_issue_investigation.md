Investigating current code + docs for 1010 pattern first — phase 1 evidence gathering.


Searched code, found files, read 3 files
Investigation
Confirmed from code + prior session's live probes (see project_m1_1010_block_debug_state.md):

Ruled out (each tested live, isolated):

Request shape/headers — Gelato client already sends proper User-Agent.
Single create/delete calls — always succeed in isolation.
Full delete→create→create→delete cycle for one candidate — succeeded once in isolation.
inter_candidate_delay (5s, commit a3bded9) — didn't fix it; 1010 hit the first candidate before any delay applied.
Gelato-specific bug — same 1010 also hit api.replicate.com, a totally different Cloudflare-fronted service, shortly after.
Key unexplained evidence, still standing:

Unauthenticated HEAD to both APIs → clean (401/404, no block).
Same calls, but authenticated, inside the real pipeline loop → intermittent 1010, even on call #1.
Isolated authenticated single calls also come back clean.
1010 = Cloudflare's own definition: browser-fingerprint/bot-score block, not a rate-limit response — Cloudflare scores requests across its whole network, not per-site.
Given block spans two unrelated Cloudflare-fronted vendors and doesn't correlate with request shape or in-process burst pattern, root cause is very likely network/IP-level Cloudflare reputation on this machine's egress IP (residential ISP, possibly CGNAT/shared, possibly already flagged from unrelated traffic) — not a pipeline code bug. That matches why isolated probes never reproduce it (probe traffic is too light to trip the score) while a real run with several authenticated calls in a short window does.

Options
Verify via different egress IP (mobile hotspot / VPN) — cheapest test. Same code, same script, different network path. If 1010 disappears, hypothesis confirmed in minutes.
Move scheduled execution to a cloud VM — matches the spec's own architecture (discrete scheduled functions, not a local dev-machine loop). Datacenter IP typically has clean Cloudflare reputation, and this is where the pipeline needs to run for production anyway, not just for this bug.
Contact Gelato/Replicate support for allowlisting — slowest, depends on two separate vendors, no guarantee either can/will action it, but worth a support ticket in parallel since it's the "proper" long-term fix for legitimate API traffic.
Retry-with-backoff+jitter on 403/1010 — doesn't fix cause, but cheap defense-in-depth worth having regardless of which option above resolves the block, since transient CF challenges can happen to anyone.

---

# Second investigation — 2026-07-18 (Cowork session)

## What the first pass missed

"Request shape/headers ruled out" only covered the **HTTP header layer**. Cloudflare
1010 is, by Cloudflare's own definition, a **browser-signature** ban (Browser
Integrity Check / Super Bot Fight Mode) — and the signature it scores is mostly
**below** the header layer: TLS handshake fingerprint (JA3/JA4), HTTP version,
and connection behavior. None of that was ever varied in the live probes, because
every probe and every pipeline call goes through the same stack.

## Code evidence (pipeline/http.py and clients)

1. **Everything is stdlib `urllib`, one fresh TCP+TLS connection per call, HTTP/1.1
   only, no keep-alive.** `http.send()` calls `urllib.request.urlopen` per request.
   Python's ssl-module JA3 is one of the most widely blocklisted "definitely
   automated" fingerprints in Cloudflare's bot rules.
2. **The poll loop multiplies it.** `group_product.poll_until_ready` /
   primary-mockup polling: `poll_interval=3.0`, `timeout=300` → up to ~100 GETs
   per candidate, each a *brand-new* TLS handshake with that fingerprint, same
   URL, from a residential IP. A multi-candidate run = hundreds of fresh
   bot-fingerprint handshakes in minutes. This is the exact behavioral pattern
   SBFM scores against.
3. **User-Agent is inconsistent and partly incriminating:**
   - `gelato_client._headers`: `"Mozilla/5.0 (compatible; qhoto-printshop-pipeline/1.0)"`
     — claims Mozilla on a TLS handshake that is visibly not a browser →
     UA/fingerprint mismatch, a classic bot-score *increase*.
   - `replicate_client._predict`: **no User-Agent at all** → urllib default
     `Python-urllib/3.x`. BIC explicitly targets missing/non-standard UAs.
   - `http.fetch_bytes` and the raw `urlopen` calls in
     `anthropic_client.py:100-107`: also default UA.

## Revised root cause

Not IP reputation *alone*: **fingerprint × behavior × IP**. Cloudflare's score
combines a known-bot TLS fingerprint, a high fresh-connection rate (3s polling,
no keep-alive), inconsistent/default UAs, and a residential (possibly CGNAT) IP.
Light isolated probes stay under the threshold; a real run crosses it. Once
tripped, the ban lingers against that fingerprint+IP, which is why 1010 then
hits call #1 of the *next* run and a second, unrelated CF-fronted vendor
(Replicate) — consistent with everything observed, without requiring the IP to
have been pre-flagged.

## Fix plan (ordered, all legitimate — no fingerprint spoofing)

1. **Rewrite `pipeline/http.py` on `httpx` with a shared `Client(http2=True)`**
   (module-level, reused across calls). One TLS handshake per run instead of one
   per request; HTTP/2 multiplexed connection ≈ well-behaved modern client, not
   the canonical urllib bot signature. `http.py` is already the single choke
   point, so the change is contained (plus the two stray `urlopen`s in
   `anthropic_client.py`). Dependency add: `httpx[http2]`.
2. **One honest UA everywhere**, set once in the shared client:
   `qhoto-printshop/1.0 (+qvajda@hotmail.fr)`. Drop the fake `Mozilla/5.0`.
3. **Calm the poll:** `poll_interval` 3s → 10s + jitter (Gelato readiness takes
   tens of seconds anyway; 3s buys nothing). Cuts request volume ~3x.
4. **Backoff on 403/1010:** long waits (60s+, doubling, cap 3), never tight
   retries — hammering a 1010 worsens the score. Log the `CF-Ray` response
   header on every 403 (extend `HTTPError` to carry headers) — needed for step 6.
5. **Egress-IP A/B test** (hotspot/VPN, same script) — still worth 10 minutes to
   size the residual IP component after 1–3 land.
6. **Support tickets to Gelato + Replicate** with CF-Ray IDs: authenticated API
   traffic being 1010-banned is their WAF misconfig; both can add allow rules
   for API-key-bearing requests. Parallel, not blocking.
7. **Production egress = cloud VM/scheduled functions** per spec architecture.
   Note: datacenter ASNs are not automatically clean for SBFM ("likely
   automated" category), so 1–4 are still required; don't treat the VM as the fix.

Explicitly rejected: `curl_cffi`/browser-TLS impersonation. It would likely
work, but it's fingerprint spoofing — fragile, and the wrong posture for
authenticated first-party API traffic that vendors should simply allow.

## Status

Analysis only — no pipeline code changed in this session. Steps 1–4 are one
contained changeset (http.py + client UA cleanup + poll/backoff constants),
est. under an hour incl. re-running the 312-test suite with a mocked client.