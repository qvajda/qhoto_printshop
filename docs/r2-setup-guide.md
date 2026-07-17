# Cloudflare R2 setup — base artwork bucket

One-time manual setup so the pipeline has a durable, publicly-fetchable home for
each candidate's base master (see PRD `2026-07-17-base-artwork-persistence-prd.md`).
Everything below is done by you in the Cloudflare dashboard; the pipeline only
reads the resulting credentials from `.env`. ~15 minutes.

Decisions this guide bakes in (from PRD §8): **non-listable public bucket**,
**retain objects for now**, base master only (mockups stay local).

---

## 1. Create a Cloudflare account + enable R2

1. Sign up / log in at <https://dash.cloudflare.com>.
2. Left sidebar → **R2** (under "Storage & Databases" — labelled "R2 Object
   Storage"). First use asks you to add a payment method even on the free tier;
   the 10 GB storage / free egress allowance covers this project comfortably for
   now.

## 2. Create the bucket

1. **Create bucket**.
2. Name: something dedicated and obvious, e.g. `qhoto-base-artwork`.
   (Bucket name is not the public hostname — that's set in step 4 — so it can be
   plain.)
3. Location: **Automatic** is fine. Leave default storage class (Standard).
4. Create.

## 3. Confirm the layout the pipeline expects

No action — just so it matches the code. The pipeline writes one object per
candidate at key:

```
base/<candidate_id>.png
```

It overwrites the same key on a generate-retry, and reuses an existing object
rather than re-uploading (idempotent). Nothing else is written to this bucket.

## 4. Expose a non-listable public URL

The goal: Gelato can **fetch** `https://<host>/base/123.png`, but nobody can
**list** the bucket's contents. R2 gives you this without making the bucket
"browsable".

Option A — **r2.dev public dev URL** (simplest, good to start):

1. Open the bucket → **Settings** → **Public access** → **R2.dev subdomain** →
   **Allow Access** (confirm the prompt).
2. Cloudflare shows a public base URL like
   `https://pub-<hash>.r2.dev`. Objects are then reachable at
   `https://pub-<hash>.r2.dev/base/<candidate_id>.png`.
3. This exposes objects **by exact key only** — there is no directory index, so
   the bucket is not listable. That satisfies the "non-listable public" decision.

Option B — **custom domain** (do later if you want your own hostname): bucket →
Settings → **Custom Domains** → connect a subdomain you own (e.g.
`art.yourdomain.com`). Same non-listable behaviour, nicer URL. Not needed for v1.

> Keep **Block public listing** behaviour as-is (R2 never exposes a listing index
> by default). Do **not** enable any third-party "bucket browser". Public =
> "fetchable by key", not "browsable".

Record the public base URL — it becomes `R2_PUBLIC_BASE_URL` below.

## 5. Create an API token scoped to this bucket

1. R2 → **Manage R2 API Tokens** (top-right of the R2 overview, or
   **Account API Tokens** → R2).
2. **Create API token**.
3. Permissions: **Object Read & Write** (the pipeline needs to put/read objects).
4. **Scope to a specific bucket** → select `qhoto-base-artwork`. (Least
   privilege — the token can't touch anything else in the account.)
5. TTL: leave as no-expiry for now, or set a long one and diarise a rotation.
6. Create. Cloudflare shows, **once**:
   - **Access Key ID**
   - **Secret Access Key**
   - the **S3 API endpoint** (`https://<ACCOUNT_ID>.r2.cloudflarestorage.com`)

   Copy all three now — the secret is not shown again.

## 6. Put the credentials in `.env`

Add to the repo's git-ignored `.env` (never commit these — same rule as the
Gelato/Etsy/Telegram secrets):

```
R2_ACCOUNT_ID=<your account id>
R2_ACCESS_KEY_ID=<access key id from step 5>
R2_SECRET_ACCESS_KEY=<secret access key from step 5>
R2_BUCKET=qhoto-base-artwork
R2_ENDPOINT=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
R2_PUBLIC_BASE_URL=https://pub-<hash>.r2.dev
```

The matching keys (with blank values) will also be added to `.env.example` so
the requirement is documented without leaking secrets.

## 7. Smoke test (after the code lands)

The build will include a tiny check that:

1. PUTs a test object to `base/_healthcheck.png`,
2. GETs `${R2_PUBLIC_BASE_URL}/base/_healthcheck.png` and confirms 200 + bytes
   match,
3. confirms a bare `GET ${R2_PUBLIC_BASE_URL}/` does **not** return a listing.

If all three pass, Gelato will be able to fetch base artwork and the bucket isn't
exposing its contents.

---

### Cost check (reminder, per PRD §6)
Storage ~$0.015/GB-month, **zero egress**, 10 GB free. At ~15 MB/master you're
well inside free tier until you're generating at real volume; retention gets
revisited then. Mockups do **not** go here — they stay local — which is what
keeps you under 10 GB.
