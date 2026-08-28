# GL-20 — `poll_until_ready` latency measurement (2026-08-28)

Sortie #40. Measured with `scripts/gelato_ready_latency.py` — read-only, GETs
each `group_products.gelato_product_id` from Gelato and computes
`max(productImages[].updatedAt) - product.createdAt`. This is a **lower
bound** on what `poll_until_ready` actually waits for: it can't see
`_image_is_fetchable`'s real S3 GET lag (`pipeline/group_product.py`), the
race the 2026-07-17 live probe found. 8 of the 41 stored product IDs 404'd
(likely deleted/orphaned products from failed-create retries) and were
excluded from the sample.

## Raw table

| product_id | lag_s | images |
|---|---|---|
| c0080773-5932-4987-b6ca-4adcc4f827ce | 53.0 | 4 |
| 49f115f2-6436-43bc-b14f-773b1066461a | 279.0 | 4 |
| 5e15c0b4-dfa4-4e82-8c9a-1b0ec45b9d41 | 2837.0 | 6 |
| 3e7abdce-c055-4609-ae68-aab19868c5a0 | 178.0 | 6 |
| 6bd740bb-f38a-428e-bab2-5672c0c619ae | 929.0 | 6 |
| 0d2493ad-df56-4f26-9f46-5c05c97407ec | 88.0 | 6 |
| e3f1ccb1-cb85-43dd-bdae-e137fa97bf15 | 135.0 | 6 |
| 885eadf1-97d3-4334-b312-2e55c77d79c5 | 67.0 | 6 |
| 72065925-5832-44ee-b9d3-d8bd563d70db | 510.0 | 6 |
| 19fe7656-fbca-44d1-b4d8-0d1d5175e732 | 43.0 | 5 |
| 1c47f411-65b2-477e-aea0-7489678dc6b9 | 80.0 | 5 |
| bf22ccf9-ddd8-4937-8dcd-b258a86ca3ad | 178.0 | 6 |
| 39be32e4-705a-4fc8-b7a1-146204089eca | 685.0 | 4 |
| fefc2698-5fae-4481-b72b-f251e57b3b9a | 45.0 | 5 |
| 85b06f6e-dde5-4776-8987-dbd456e54a88 | 50.0 | 6 |
| 65580dc4-ca54-41e4-a1e7-49fde4a136c3 | 42.0 | 6 |
| 630e9300-69a4-409e-a9e3-5ea13a198fee | 46.0 | 5 |
| 3b9b88ed-3cf5-4708-b385-22aac6ca41e1 | 51.0 | 6 |
| 07131de1-be7f-4984-93f9-6ebaae0ba5c9 | 40.0 | 6 |
| 3f5a6899-5f43-4ef1-8f20-987fd656f018 | 42.0 | 6 |
| 7367ef4f-3c51-400a-8a7a-543d5481bfd9 | 96.0 | 6 |
| 6a97a1e8-e5cd-460d-bc05-3ae5049cc3f9 | 222.0 | 5 |
| c0d64b9a-9310-4670-bf96-1051f48bf5e0 | 85.0 | 6 |
| ab2e7e41-7227-4521-b472-21de33ce86b9 | 135.0 | 6 |
| b8f662fa-8ee9-4382-821b-1ec3ea1cc5d0 | 43.0 | 5 |
| e011b53c-07b2-4d8b-a17a-91bb5036ed85 | 49.0 | 6 |
| 8989020b-b935-4678-b65c-c220f62afdaa | 1008.0 | 6 |
| ef2565ef-bd99-4221-b1f6-cd0f2e77e11e | 323.0 | 6 |
| 990237f3-ed3a-4bcf-985f-7cfcededd2db | 45.0 | 6 |
| d6a135fc-e374-4ef6-89cc-c68ff212a853 | 681.0 | 6 |
| 03f3dbba-bac6-49de-8e80-b67249e6cc67 | 3904.0 | 6 |
| ae5b5351-6aa3-4827-90ed-1d34b8b0aaae | 58.0 | 6 |
| ebaaaf9d-899c-4429-ae6d-bcf1f24b3bc5 | 139.0 | 6 |

8 IDs (`0ea813f6…`, `f57cb26b…`, `17414abd…`, `1bc0abf3…`, `bb112977…`,
`587d3a75…`, `7bdf4721…`, `0e6bbc77…`) returned Gelato `404 NOT_FOUND` — not
counted.

## Summary

n=33, min=40.0s, median=88.0s, p90=685.0s, max=3904.0s

## Verdict: current values already tight — no change

`poll_until_ready`'s current default is `timeout=300.0`. The measured lag
(a **lower bound** on the real wait) exceeds 300s in 6 of 33 products, up to
**3904s (65 min)** on `03f3dbba-bac6-49de-8e80-b67249e6cc67` — over 13x the
current timeout. `p90=685s` already clears the current default. The one
known real 300s timeout in `logs/batch.log:34`
(`6bd740bb-f38a-428e-bab2-5672c0c619ae`) is in this sample at 929s, confirming
the proxy and the log agree on direction.

The board row's premise — that the self-hosted gallery made Gelato's
readiness poll shortenable — does not hold: real Gelato rehost lag is
routinely longer than what the pipeline already waits for, not shorter.
Shortening `poll_interval` / `timeout` would strand more groups on a false
timeout, not fewer. No change to `pipeline/group_product.py`. Closing this
row with the measurement recorded; a *lengthening* of the timeout is a
separate, unrelated defect this row does not open (out of scope: this row
was about relaxation, not about fixing under-timeout groups).
