# Variant-Listing Migration (fix-plan item 6 + 7/8/10/11) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the per-size Gelato-product/Etsy-listing model with the v4.11 model: one Gelato product + one Etsy listing per aspect-ratio group, with each group's sizes as Etsy variants (own per-variant price), and Etsy `updateListing`/`updateListingInventory` PATCH replacing the removed `create_draft_listing` create path ("Gelato pushes, we patch").

**Architecture:** `group_products` becomes a group-level row (one Gelato product/Etsy listing id per aspect-ratio group) with a new child table `group_product_variants` holding the per-size price/template-variant data. A new shared module `pipeline/group_product.py` centralizes create-or-reuse (idempotent Gelato create across N variants), Etsy `listing_id` resolution (polling Gelato's `externalId`, ~8 min lag per live probe), and the Etsy patch step — used by all three existing call sites (`primary_mockup.py`, `publish_primary_group.py`, `group_mockup.py`/`publish_group.py`) instead of each duplicating create/publish logic.

**Tech Stack:** Python, SQLite, Gelato Ecommerce API v1, Etsy Open API v3.

## Global Constraints

- Image generation is FLUX.1 [schnell] only, never [dev] — untouched by this plan, no generation code changes.
- A design is generated once; group-level crop/retry reuses the same base image — untouched by this plan.
- Never call `etsy_client.create_draft_listing` from any publish path (CLAUDE.md hard constraint). It stays defined (still covered by `tests/test_etsy_client.py`) but must have zero callers after this plan.
- Gelato create must be idempotent: reuse a stored `gelato_product_id` before creating; delete orphans on a failed-create retry. Route all create paths through one shared helper (`group_product.create_or_reuse_group_product`).
- If a still-placeholder `template_id`/`template_variant_id` ever reaches a real (non-mocked) `products:create-from-template` call, fail loudly — never silently skip. `gelato_client.create_product_from_template` already does this per-variant; the multi-variant version must check every variant, not just the first.
- Critic-pass retry cap is exactly 3 attempts per group, then abandon that group only (primary group additionally triggers Go/Hold/Kill fallback) — untouched by this plan, but `critic_pass.discard_superseded_attempt` must still correctly delete the (now group-level) Gelato product.
- Static config (`config/static_config.json`) is resolved once, never discovered at runtime — no changes to its shape needed; it already has per-size `gelato_templates` keys and a group→sizes `aspect_ratio_groups` map.
- Shop currency EUR, `who_made: i_did`, `is_supply: false`, `when_made: made_to_order`, `shop_section_id: 59380312`, `production_partner_ids: [5717252]`, `taxonomy_id: 1027` — set via the listing patch, not create.

---

## File Structure

- **Modify** `db/schema.sql` — `group_products` becomes group-level; new `group_product_variants` table.
- **Modify** `pipeline/gelato_client.py` — `create_product_from_template` takes a list of variants; add `get_etsy_listing_id`.
- **Modify** `pipeline/etsy_client.py` — add `update_listing`, `get_listing_inventory`, `update_listing_inventory`.
- **Create** `pipeline/group_product.py` — shared create-or-reuse, listing-id resolution, Etsy patch, used by every group-publish call site.
- **Modify** `pipeline/primary_mockup.py` — delegate the 8x12 pre-review product to `group_product.py`.
- **Modify** `pipeline/publish_primary_group.py` — one Gelato product / one Etsy listing for the whole primary group (8x12+A3+A2+A1).
- **Modify** `pipeline/group_mockup.py` — delegate 5x7/10x24 group product creation to `group_product.py`.
- **Modify** `pipeline/publish_group.py` — patch (not create-draft) the 5x7/10x24 group's listing on approve.
- **Modify** `pipeline/critic_pass.py` — cascade-delete `group_product_variants` in `discard_superseded_attempt`.
- **Modify** `pipeline/cleanup.py` — cascade-delete `group_product_variants` alongside `product_images`/`group_products`.
- **Modify** `pipeline/digest.py`, `pipeline/group_digest.py` — render per-size prices (a group now has 1-4 prices, not one).
- **Modify** `pipeline/compliance_draft.py` — drop the per-size title-suffix headroom (titles no longer get a size suffix).

---

### Task 1: DB schema migration

**Files:**
- Modify: `db/schema.sql:61-76` (the `group_products` table)
- Test: `tests/test_db.py`

**Interfaces:**
- Produces: `group_products(id, group_id, gelato_template_id, gelato_product_id, etsy_listing_id, title, status, created_at, updated_at)` — one row per `groups.id`, no `size`/`price_eur`/`orientation` columns anymore.
- Produces: `group_product_variants(id, group_product_id, size, orientation, gelato_template_variant_id, price_eur, created_at)` — one row per size within a group, `UNIQUE(group_product_id, size)`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_db.py` (follow whatever fixture pattern the existing file uses, e.g. `db.get_connection(tmp_path / "test.sqlite3")` + `db.init_db(conn)`):

```python
def test_group_products_is_group_level_not_size_level(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)

    cols = {row["name"] for row in conn.execute("PRAGMA table_info(group_products)").fetchall()}
    assert "size" not in cols
    assert "price_eur" not in cols
    assert "orientation" not in cols
    assert {"gelato_product_id", "etsy_listing_id", "title", "status"} <= cols


def test_group_product_variants_table_exists_with_unique_size_per_product(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)

    timestamp = "2026-07-16T00:00:00"
    conn.execute(
        "INSERT INTO candidates (created_at, niche, go_hold_kill, status, updated_at) "
        "VALUES (?, 'test', 'go', 'pending', ?)", (timestamp, timestamp),
    )
    conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (1, 'primary', 'pending_generation', ?, ?)", (timestamp, timestamp),
    )
    conn.execute(
        "INSERT INTO group_products (group_id, gelato_template_id, status, created_at, updated_at) "
        "VALUES (1, 'tmpl1', 'pending', ?, ?)", (timestamp, timestamp),
    )
    conn.execute(
        "INSERT INTO group_product_variants "
        "(group_product_id, size, orientation, gelato_template_variant_id, price_eur, created_at) "
        "VALUES (1, '8x12', 'portrait', 'var1', 24.0, ?)", (timestamp,),
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO group_product_variants "
            "(group_product_id, size, orientation, gelato_template_variant_id, price_eur, created_at) "
            "VALUES (1, '8x12', 'portrait', 'var1', 99.0, ?)", (timestamp,),
        )
```

Add `import sqlite3` and `import pytest` to `tests/test_db.py` if not already present (check first).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_db.py -v -k "group_products_is_group_level or group_product_variants_table"`
Expected: FAIL (`size` still a column; `group_product_variants` table doesn't exist).

- [ ] **Step 3: Rewrite the schema**

Replace `db/schema.sql:61-76`:

```sql
CREATE TABLE IF NOT EXISTS group_products (
  id INTEGER PRIMARY KEY,
  group_id INTEGER NOT NULL REFERENCES groups(id),
  gelato_template_id TEXT NOT NULL,
  gelato_product_id TEXT,
  etsy_listing_id TEXT,
  title TEXT,
  status TEXT NOT NULL CHECK(status IN (
    'pending','created','mockup_failed','publish_failed','published','deleted'
  )),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS group_product_variants (
  id INTEGER PRIMARY KEY,
  group_product_id INTEGER NOT NULL REFERENCES group_products(id),
  size TEXT NOT NULL CHECK(size IN ('5x7','8x12','A3','A2','10x24','A1')),
  orientation TEXT NOT NULL CHECK(orientation IN ('portrait','landscape')),
  gelato_template_variant_id TEXT NOT NULL,
  price_eur REAL NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(group_product_id, size)
);
```

`product_images.group_product_id` and `listing_metrics_snapshots.group_product_id` (lines 78-85, 104-111) keep their existing FK target unchanged — they now mean "images/metrics for the group's one listing," which is already correct (a group has one shared mockup gallery).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_db.py -v`
Expected: PASS, full file green (check no other test in this file still asserts the old per-size columns — fix any that do, e.g. a schema-dump test).

- [ ] **Step 5: Commit**

```bash
git add db/schema.sql tests/test_db.py
git commit -m "feat: migrate group_products to group-level schema, add group_product_variants"
```

---

### Task 2: `gelato_client.py` — multi-variant create + listing-id resolution

**Files:**
- Modify: `pipeline/gelato_client.py:37-92` (`create_product_from_template`)
- Modify: `pipeline/gelato_client.py` (add `get_etsy_listing_id`)
- Test: `tests/test_gelato_client.py`

**Interfaces:**
- Consumes: nothing new (same `http.send`, `config.require_env`, `config.is_placeholder`).
- Produces: `create_product_from_template(template_id: str, variants: list[dict], title: str, *, store_id=None, api_key=None, dry_run=None) -> dict` where each variant dict is `{"template_variant_id": str, "image_placeholder_name": str, "image_url": str}`. Response shape unchanged (`{"id": ..., ...}`).
- Produces: `get_etsy_listing_id(product_id: str, *, store_id=None, api_key=None) -> str | None` — `None` if `externalId` not yet populated (Gelato→Etsy sync lag).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_gelato_client.py` (match existing mocking style in that file, e.g. `patch("pipeline.http.send")` or similar — check the file first for the exact pattern used by existing `create_product_from_template` tests, then follow it):

```python
def test_create_product_from_template_builds_one_variant_entry_per_size():
    variants = [
        {"template_variant_id": "var-8x12", "image_placeholder_name": "ph1", "image_url": "https://x/a.png"},
        {"template_variant_id": "var-a3", "image_placeholder_name": "ph1", "image_url": "https://x/a.png"},
    ]
    with patch("pipeline.http.send") as mock_send:
        mock_send.return_value = {"id": "prod123"}
        gelato_client.create_product_from_template(
            "tmpl1", variants, "Test Title", store_id="store1", api_key="key1", dry_run=False,
        )

    sent_request = mock_send.call_args[0][0]
    body = json.loads(sent_request.data)
    assert len(body["variants"]) == 2
    assert body["variants"][0]["templateVariantId"] == "var-8x12"
    assert body["variants"][1]["templateVariantId"] == "var-a3"
    assert body["variants"][0]["imagePlaceholders"] == [{"name": "ph1", "fileUrl": "https://x/a.png"}]


def test_create_product_from_template_dry_run_ignores_variant_count():
    result = gelato_client.create_product_from_template(
        "tmpl1", [{"template_variant_id": "v1", "image_placeholder_name": "ph1", "image_url": "u1"}],
        "Test Title", dry_run=True,
    )
    assert result["_dry_run"] is True


def test_create_product_from_template_refuses_placeholder_in_any_variant():
    variants = [
        {"template_variant_id": "REAL_VAR", "image_placeholder_name": "ph1", "image_url": "u1"},
        {"template_variant_id": "PLACEHOLDER_VAR", "image_placeholder_name": "ph1", "image_url": "u1"},
    ]
    with pytest.raises(gelato_client.GelatoPlaceholderTemplateError):
        gelato_client.create_product_from_template("tmpl1", variants, "Test Title", dry_run=False)


def test_get_etsy_listing_id_returns_external_id_when_present():
    with patch("pipeline.gelato_client.get_product") as mock_get:
        mock_get.return_value = {"id": "prod123", "externalId": "etsy-listing-999"}
        result = gelato_client.get_etsy_listing_id("prod123", store_id="store1", api_key="key1")
    assert result == "etsy-listing-999"


def test_get_etsy_listing_id_returns_none_when_not_yet_synced():
    with patch("pipeline.gelato_client.get_product") as mock_get:
        mock_get.return_value = {"id": "prod123", "externalId": None}
        result = gelato_client.get_etsy_listing_id("prod123")
    assert result is None
```

Add `import json` and `import pytest` at the top of `tests/test_gelato_client.py` if not already present.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_gelato_client.py -v -k "multi_variant or variant_count or any_variant or listing_id"`
Expected: FAIL (`create_product_from_template` still takes `template_variant_id`/`image_placeholder_name`/`image_url` as single scalars; `get_etsy_listing_id` doesn't exist).

- [ ] **Step 3: Rewrite `create_product_from_template`, add `get_etsy_listing_id`**

Replace `pipeline/gelato_client.py:37-92`:

```python
def create_product_from_template(
    template_id: str,
    variants: list,
    title: str,
    *,
    store_id: str = None,
    api_key: str = None,
    dry_run: bool = None,
) -> dict:
    if dry_run is None:
        dry_run = not config.is_live_mode("GELATO")

    if dry_run:
        return {
            "id": "DRY_RUN_PRODUCT_ID",
            "storeId": store_id or "DRY_RUN_STORE_ID",
            "title": title,
            "status": "created",
            "previewUrl": None,
            "productImages": [],
            "isReadyToPublish": False,
            "_dry_run": True,
        }

    for variant in variants:
        for label in ("template_variant_id", "image_placeholder_name"):
            value = variant[label]
            if config.is_placeholder(value):
                raise GelatoPlaceholderTemplateError(
                    f"Refusing to create a real Gelato product with a placeholder "
                    f"{label} ({value!r}). Fill in the real value in "
                    f"config/static_config.json before making a live call."
                )
    if config.is_placeholder(template_id):
        raise GelatoPlaceholderTemplateError(
            f"Refusing to create a real Gelato product with a placeholder "
            f"template_id ({template_id!r}). Fill in the real value in "
            f"config/static_config.json before making a live call."
        )

    api_key = api_key or config.require_env("GELATO_API_KEY")
    store_id = store_id or config.require_env("GELATO_STORE_ID")
    url = f"{GELATO_API_BASE}/stores/{store_id}/products:create-from-template"
    body = json.dumps({
        "templateId": template_id,
        "title": title,
        "isVisibleInTheOnlineStore": False,
        "variants": [
            {
                "templateVariantId": variant["template_variant_id"],
                "imagePlaceholders": [
                    {"name": variant["image_placeholder_name"], "fileUrl": variant["image_url"]}
                ],
            }
            for variant in variants
        ],
    }).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=_headers(api_key), method="POST")
    return http.send(request)


def get_etsy_listing_id(product_id: str, *, store_id: str = None, api_key: str = None) -> str | None:
    product = get_product(product_id, store_id=store_id, api_key=api_key)
    return product.get("externalId") or None


def delete_product(product_id: str, *, store_id: str = None, api_key: str = None, dry_run: bool = None) -> None:
    if dry_run is None:
        dry_run = not config.is_live_mode("GELATO")

    if dry_run:
        return

    api_key = api_key or config.require_env("GELATO_API_KEY")
    store_id = store_id or config.require_env("GELATO_STORE_ID")
    url = f"{GELATO_API_BASE}/stores/{store_id}/products/{product_id}"
    request = urllib.request.Request(url, headers=_headers(api_key), method="DELETE")
    http.send(request)
```

(`get_etsy_listing_id` inserted before `delete_product`; `delete_product` itself is unchanged, just reproduced above so the file stays contiguous.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_gelato_client.py -v`
Expected: PASS, full file green.

- [ ] **Step 5: Commit**

```bash
git add pipeline/gelato_client.py tests/test_gelato_client.py
git commit -m "feat: gelato_client supports multi-variant create and Etsy listing_id resolution"
```

---

### Task 3: `etsy_client.py` — `update_listing`, `get_listing_inventory`, `update_listing_inventory`

**Files:**
- Modify: `pipeline/etsy_client.py` (add three functions after `update_listing_state`, i.e. after line 102)
- Test: `tests/test_etsy_client.py`

**Interfaces:**
- Produces: `update_listing(shop_id: str, listing_id: str, listing_data: dict, *, api_key=None, api_secret=None, access_token=None, dry_run=None) -> dict` — PATCH full field set (title/description/tags/taxonomy_id/who_made/when_made/is_supply/shop_section_id/production_partner_ids).
- Produces: `get_listing_inventory(shop_id: str, listing_id: str, *, api_key=None, api_secret=None, access_token=None, dry_run=None) -> dict` — GET current inventory (`{"products": [...]}`).
- Produces: `update_listing_inventory(shop_id: str, listing_id: str, size_to_price: dict, *, api_key=None, api_secret=None, access_token=None, dry_run=None) -> dict` — fetches inventory, matches each product's `property_values` against the `size_to_price` keys (case-insensitive substring match against each `property_values[].values[]` entry), sets that product's `offerings[0]["price"]`, strips `product_id`/`is_deleted`/`offering_id`/`scale_name` (read-only response fields Etsy rejects on write-back), PUTs the result. Raises `ValueError` if any key in `size_to_price` matches zero products (fail loud, never silently skip a size).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_etsy_client.py`:

```python
def test_update_listing_patches_full_field_set():
    listing_data = {
        "title": "Monstera Line Art", "description": "desc", "tags": ["a", "b"],
        "taxonomy_id": 1027, "who_made": "i_did", "when_made": "made_to_order",
        "is_supply": False, "shop_section_id": 59380312, "production_partner_ids": [5717252],
    }
    with patch("pipeline.http.send") as mock_send:
        mock_send.return_value = {"listing_id": 555, **listing_data}
        result = etsy_client.update_listing(
            "shop1", "555", listing_data, api_key="k", api_secret="s", access_token="t", dry_run=False,
        )

    sent_request = mock_send.call_args[0][0]
    assert sent_request.method == "PATCH"
    assert sent_request.full_url == "https://openapi.etsy.com/v3/application/shops/shop1/listings/555"
    body = json.loads(sent_request.data)
    assert body == listing_data
    assert result["listing_id"] == 555


def test_update_listing_dry_run_does_not_call_http():
    with patch("pipeline.http.send") as mock_send:
        result = etsy_client.update_listing("shop1", "555", {"title": "x"}, dry_run=True)
    mock_send.assert_not_called()
    assert result["_dry_run"] is True


def test_get_listing_inventory_sends_get():
    with patch("pipeline.http.send") as mock_send:
        mock_send.return_value = {"products": []}
        etsy_client.get_listing_inventory("shop1", "555", api_key="k", api_secret="s",
                                           access_token="t", dry_run=False)
    sent_request = mock_send.call_args[0][0]
    assert sent_request.method == "GET"
    assert sent_request.full_url == "https://openapi.etsy.com/v3/application/listings/555/inventory"


def test_update_listing_inventory_sets_price_on_matching_size_and_strips_readonly_fields():
    inventory = {
        "products": [
            {
                "product_id": 1, "sku": "", "is_deleted": False,
                "property_values": [{"property_id": 100, "property_name": "Size",
                                      "value_ids": [1], "scale_id": None, "scale_name": None,
                                      "values": ["8x12"]}],
                "offerings": [{"offering_id": 10, "price": {"amount": 2000, "divisor": 100, "currency_code": "EUR"},
                               "quantity": 999, "is_enabled": True}],
            },
            {
                "product_id": 2, "sku": "", "is_deleted": False,
                "property_values": [{"property_id": 100, "property_name": "Size",
                                      "value_ids": [2], "scale_id": None, "scale_name": None,
                                      "values": ["A3"]}],
                "offerings": [{"offering_id": 11, "price": {"amount": 3000, "divisor": 100, "currency_code": "EUR"},
                               "quantity": 999, "is_enabled": True}],
            },
        ]
    }
    with patch("pipeline.etsy_client.get_listing_inventory") as mock_get, \
         patch("pipeline.http.send") as mock_send:
        mock_get.return_value = inventory
        mock_send.return_value = {"products": []}
        etsy_client.update_listing_inventory(
            "shop1", "555", {"8x12": 24.0, "A3": 35.0},
            api_key="k", api_secret="s", access_token="t", dry_run=False,
        )

    sent_request = mock_send.call_args[0][0]
    assert sent_request.method == "PUT"
    body = json.loads(sent_request.data)
    prices = {p["property_values"][0]["values"][0]: p["offerings"][0]["price"] for p in body["products"]}
    assert prices["8x12"] == 24.0
    assert prices["A3"] == 35.0
    assert "product_id" not in body["products"][0]
    assert "is_deleted" not in body["products"][0]
    assert "offering_id" not in body["products"][0]["offerings"][0]


def test_update_listing_inventory_raises_if_a_size_has_no_matching_product():
    inventory = {"products": [{"product_id": 1, "sku": "", "is_deleted": False,
                                "property_values": [{"property_id": 100, "property_name": "Size",
                                                      "value_ids": [1], "scale_id": None, "scale_name": None,
                                                      "values": ["8x12"]}],
                                "offerings": [{"offering_id": 10,
                                               "price": {"amount": 2000, "divisor": 100, "currency_code": "EUR"},
                                               "quantity": 999, "is_enabled": True}]}]}
    with patch("pipeline.etsy_client.get_listing_inventory") as mock_get:
        mock_get.return_value = inventory
        with pytest.raises(ValueError, match="A1"):
            etsy_client.update_listing_inventory("shop1", "555", {"8x12": 24.0, "A1": 49.0}, dry_run=False)
```

Add `import json` and `import pytest` to `tests/test_etsy_client.py` if not already present.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_etsy_client.py -v -k "update_listing or listing_inventory"`
Expected: FAIL (`AttributeError: module 'pipeline.etsy_client' has no attribute 'update_listing'`, etc.).

- [ ] **Step 3: Write the implementation**

Insert into `pipeline/etsy_client.py` after `update_listing_state` (after line 102):

```python
def update_listing(
    shop_id: str, listing_id: str, listing_data: dict, *, api_key: str = None, api_secret: str = None,
    access_token: str = None, dry_run: bool = None
) -> dict:
    if dry_run is None:
        dry_run = not config.is_live_mode("ETSY")

    if dry_run:
        return {"listing_id": listing_id, "_dry_run": True, **listing_data}

    api_key = api_key or config.require_env("ETSY_API_KEY")
    api_secret = api_secret or config.require_env("ETSY_API_SECRET")
    access_token = access_token or config.require_env("ETSY_ACCESS_TOKEN")
    url = f"{ETSY_API_BASE}/shops/{shop_id}/listings/{listing_id}"
    body = json.dumps(listing_data).encode("utf-8")
    headers = _headers(api_key, api_secret, access_token)
    headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method="PATCH")
    return http.send(request)


def get_listing_inventory(
    shop_id: str, listing_id: str, *, api_key: str = None, api_secret: str = None,
    access_token: str = None, dry_run: bool = None
) -> dict:
    if dry_run is None:
        dry_run = not config.is_live_mode("ETSY")

    if dry_run:
        return {"products": [], "_dry_run": True}

    api_key = api_key or config.require_env("ETSY_API_KEY")
    api_secret = api_secret or config.require_env("ETSY_API_SECRET")
    access_token = access_token or config.require_env("ETSY_ACCESS_TOKEN")
    url = f"{ETSY_API_BASE}/listings/{listing_id}/inventory"
    request = urllib.request.Request(url, headers=_headers(api_key, api_secret, access_token), method="GET")
    return http.send(request)


_INVENTORY_READONLY_PRODUCT_FIELDS = ("product_id", "is_deleted")
_INVENTORY_READONLY_OFFERING_FIELDS = ("offering_id",)


def update_listing_inventory(
    shop_id: str, listing_id: str, size_to_price: dict, *, api_key: str = None, api_secret: str = None,
    access_token: str = None, dry_run: bool = None
) -> dict:
    if dry_run is None:
        dry_run = not config.is_live_mode("ETSY")

    inventory = get_listing_inventory(
        shop_id, listing_id, api_key=api_key, api_secret=api_secret,
        access_token=access_token, dry_run=dry_run,
    )
    if dry_run:
        return {"products": [], "_dry_run": True}

    matched_sizes = set()
    products = []
    for product in inventory["products"]:
        matched_size = None
        for prop in product["property_values"]:
            for value in prop["values"]:
                for size in size_to_price:
                    if size.lower() in value.lower():
                        matched_size = size
        clean_product = {k: v for k, v in product.items() if k not in _INVENTORY_READONLY_PRODUCT_FIELDS}
        clean_product["offerings"] = [
            {k: v for k, v in offering.items() if k not in _INVENTORY_READONLY_OFFERING_FIELDS}
            for offering in product["offerings"]
        ]
        if matched_size is not None:
            matched_sizes.add(matched_size)
            for offering in clean_product["offerings"]:
                offering["price"] = size_to_price[matched_size]
        products.append(clean_product)

    missing = set(size_to_price) - matched_sizes
    if missing:
        raise ValueError(
            f"update_listing_inventory: no inventory product matched size(s) {sorted(missing)} "
            f"for listing {listing_id} — refusing to silently drop a size's price."
        )

    api_key = api_key or config.require_env("ETSY_API_KEY")
    api_secret = api_secret or config.require_env("ETSY_API_SECRET")
    access_token = access_token or config.require_env("ETSY_ACCESS_TOKEN")
    url = f"{ETSY_API_BASE}/listings/{listing_id}/inventory"
    body = json.dumps({"products": products}).encode("utf-8")
    headers = _headers(api_key, api_secret, access_token)
    headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method="PUT")
    return http.send(request)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_etsy_client.py -v`
Expected: PASS, full file green.

- [ ] **Step 5: Commit**

```bash
git add pipeline/etsy_client.py tests/test_etsy_client.py
git commit -m "feat: etsy_client update_listing + inventory-price patch functions"
```

---

### Task 4: New `pipeline/group_product.py` — shared create-or-reuse + patch

**Files:**
- Create: `pipeline/group_product.py`
- Test: `tests/test_group_product.py`

**Interfaces:**
- Consumes: `config.get_template_variant`, `config.is_live_mode`, `gelato_client.create_product_from_template`, `gelato_client.get_product`, `gelato_client.get_etsy_listing_id`, `gelato_client.delete_product`, `etsy_client.update_listing`, `etsy_client.update_listing_inventory`.
- Produces: `class GelatoMockupTimeoutError(Exception)`, `class EtsyListingSyncTimeoutError(Exception)`.
- Produces: `poll_until_ready(product_id, *, store_id=None, api_key=None, poll_interval=3.0, timeout=90.0, sleep_fn=time.sleep, now_fn=time.monotonic) -> dict`.
- Produces: `resolve_etsy_listing_id(product_id, *, store_id=None, api_key=None, poll_interval=30.0, timeout=600.0, sleep_fn=time.sleep, now_fn=time.monotonic) -> str`.
- Produces: `create_or_reuse_group_product(conn, group_id, sizes, candidate, static_config, title, orientation="portrait", *, store_id=None, api_key=None, poll_interval=3.0, poll_timeout=90.0, now=None) -> dict` returns `{"group_product_id": int, "gelato_product_id": str}`. `sizes` is `list[str]`.
- Produces: `patch_etsy_listing(conn, group_product_id, group_type, listing_text, static_config, *, shop_id=None, etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None, dry_run=None, now=None) -> str` returns the resolved `etsy_listing_id`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_group_product.py` (mirror the fixture helpers from `tests/test_publish_primary_group.py`: `_fresh_conn`, `_insert_candidate`; add a `_insert_group` helper for an arbitrary `group_type`):

```python
from unittest.mock import patch

import pytest

import pipeline.config as config
import pipeline.db as db
import pipeline.group_product as group_product


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="primary_review",
                       base_image_url="https://replicate.delivery/out.png"):
    timestamp = "2026-07-16T09:00:00"
    cursor = conn.execute(
        "INSERT INTO candidates (created_at, niche, go_hold_kill, status, base_image_url, updated_at) "
        "VALUES (?, ?, 'go', ?, ?, ?)",
        (timestamp, niche, status, base_image_url, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_group(conn, candidate_id, group_type="primary", *, status="pending_review"):
    timestamp = "2026-07-16T09:05:00"
    cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (candidate_id, group_type, status, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _static_config():
    return config.load_static_config()


def test_create_or_reuse_group_product_creates_one_product_with_all_variants(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_group(conn, candidate_id)
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())
    static_config = _static_config()

    with patch("pipeline.gelato_client.create_product_from_template") as mock_create:
        mock_create.return_value = {"id": "gelato-prod-1", "_dry_run": True, "previewUrl": None, "productImages": []}
        result = group_product.create_or_reuse_group_product(
            conn, group_id, ["8x12", "A3", "A2", "A1"], candidate, static_config,
            "Monstera Line Art", now="2026-07-16T09:10:00",
        )

    assert mock_create.call_count == 1
    variants_arg = mock_create.call_args[0][1]
    assert [v["template_variant_id"] for v in variants_arg] == [
        static_config["gelato_templates"][f"{s}_portrait"]["template_variant_id"]
        for s in ("8x12", "A3", "A2", "A1")
    ]
    assert result["gelato_product_id"] == "gelato-prod-1"

    gp_row = conn.execute("SELECT * FROM group_products WHERE id = ?", (result["group_product_id"],)).fetchone()
    assert gp_row["status"] == "created"
    variant_rows = conn.execute(
        "SELECT size, price_eur FROM group_product_variants WHERE group_product_id = ? ORDER BY size",
        (result["group_product_id"],),
    ).fetchall()
    assert {r["size"]: r["price_eur"] for r in variant_rows} == {
        "8x12": static_config["prices_eur"]["8x12"], "A1": static_config["prices_eur"]["A1"],
        "A2": static_config["prices_eur"]["A2"], "A3": static_config["prices_eur"]["A3"],
    }


def test_create_or_reuse_group_product_reuses_existing_created_row(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_group(conn, candidate_id)
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())
    static_config = _static_config()

    with patch("pipeline.gelato_client.create_product_from_template") as mock_create:
        mock_create.return_value = {"id": "gelato-prod-1", "_dry_run": True, "previewUrl": None, "productImages": []}
        first = group_product.create_or_reuse_group_product(
            conn, group_id, ["8x12"], candidate, static_config, "Title", now="2026-07-16T09:10:00",
        )
        second = group_product.create_or_reuse_group_product(
            conn, group_id, ["8x12"], candidate, static_config, "Title", now="2026-07-16T09:11:00",
        )

    assert mock_create.call_count == 1
    assert first["group_product_id"] == second["group_product_id"]


def test_create_or_reuse_group_product_deletes_orphan_before_retry(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_group(conn, candidate_id)
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())
    static_config = _static_config()
    timestamp = "2026-07-16T09:10:00"

    conn.execute(
        "INSERT INTO group_products (group_id, gelato_template_id, gelato_product_id, status, created_at, updated_at) "
        "VALUES (?, 'tmpl', 'stale-gelato-id', 'publish_failed', ?, ?)",
        (group_id, timestamp, timestamp),
    )
    conn.commit()

    with patch("pipeline.gelato_client.delete_product") as mock_delete, \
         patch("pipeline.gelato_client.create_product_from_template") as mock_create:
        mock_create.return_value = {"id": "gelato-prod-new", "_dry_run": True, "previewUrl": None, "productImages": []}
        result = group_product.create_or_reuse_group_product(
            conn, group_id, ["8x12"], candidate, static_config, "Title", now=timestamp,
        )

    mock_delete.assert_called_once_with("stale-gelato-id", store_id=None, api_key=None)
    assert result["gelato_product_id"] == "gelato-prod-new"
    stale_row = conn.execute(
        "SELECT status FROM group_products WHERE gelato_product_id = 'stale-gelato-id'"
    ).fetchone()
    assert stale_row["status"] == "deleted"


def test_patch_etsy_listing_resolves_id_patches_and_sets_variant_prices(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_group(conn, candidate_id)
    static_config = _static_config()
    timestamp = "2026-07-16T09:10:00"
    conn.execute(
        "INSERT INTO group_products (group_id, gelato_template_id, gelato_product_id, status, created_at, updated_at) "
        "VALUES (?, 'tmpl', 'gelato-prod-1', 'created', ?, ?)",
        (group_id, timestamp, timestamp),
    )
    group_product_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    conn.execute(
        "INSERT INTO group_product_variants (group_product_id, size, orientation, gelato_template_variant_id, price_eur, created_at) "
        "VALUES (?, '8x12', 'portrait', 'var1', 24.0, ?)", (group_product_id, timestamp),
    )
    conn.commit()

    listing_text = {
        "title": "Monstera Line Art", "description": "desc", "tags": '["a", "b"]',
        "who_made": "i_did", "taxonomy_id": "1027", "production_partner_ids": "[5717252]",
    }

    with patch("pipeline.gelato_client.get_etsy_listing_id") as mock_resolve, \
         patch("pipeline.etsy_client.update_listing") as mock_update, \
         patch("pipeline.etsy_client.update_listing_inventory") as mock_inventory:
        mock_resolve.return_value = "etsy-listing-42"
        listing_id = group_product.patch_etsy_listing(
            conn, group_product_id, "primary", listing_text, static_config,
            shop_id="shop1", dry_run=True, now=timestamp,
        )

    assert listing_id == "etsy-listing-42"
    mock_update.assert_called_once()
    patched_data = mock_update.call_args[0][2]
    assert patched_data["title"] == "Monstera Line Art"
    assert "8x12" not in patched_data["title"]
    mock_inventory.assert_called_once_with(
        "shop1", "etsy-listing-42", {"8x12": 24.0},
        api_key=None, api_secret=None, access_token=None, dry_run=True,
    )
    gp_row = conn.execute("SELECT etsy_listing_id, status FROM group_products WHERE id = ?", (group_product_id,)).fetchone()
    assert gp_row["etsy_listing_id"] == "etsy-listing-42"
    assert gp_row["status"] == "published"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_group_product.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'pipeline.group_product'`).

- [ ] **Step 3: Write the implementation**

Create `pipeline/group_product.py`:

```python
import json
import time
from datetime import datetime, timezone

import pipeline.config as config
import pipeline.etsy_client as etsy_client
import pipeline.gelato_client as gelato_client


class GelatoMockupTimeoutError(Exception):
    pass


class EtsyListingSyncTimeoutError(Exception):
    pass


def poll_until_ready(product_id: str, *, store_id: str = None, api_key: str = None,
                      poll_interval: float = 3.0, timeout: float = 90.0,
                      sleep_fn=time.sleep, now_fn=time.monotonic) -> dict:
    deadline = now_fn() + timeout
    while True:
        product = gelato_client.get_product(product_id, store_id=store_id, api_key=api_key)
        if product.get("isReadyToPublish"):
            return product
        if now_fn() >= deadline:
            raise GelatoMockupTimeoutError(
                f"Gelato product {product_id} did not become ready to publish within "
                f"{timeout:.0f}s. The one observed real render took ~9s for a 4-image "
                f"gallery - this likely indicates a Gelato-side delay or outage, not a "
                f"pipeline bug."
            )
        sleep_fn(poll_interval)


def resolve_etsy_listing_id(product_id: str, *, store_id: str = None, api_key: str = None,
                             poll_interval: float = 30.0, timeout: float = 600.0,
                             sleep_fn=time.sleep, now_fn=time.monotonic) -> str:
    deadline = now_fn() + timeout
    while True:
        listing_id = gelato_client.get_etsy_listing_id(product_id, store_id=store_id, api_key=api_key)
        if listing_id is not None:
            return listing_id
        if now_fn() >= deadline:
            raise EtsyListingSyncTimeoutError(
                f"Gelato product {product_id}'s externalId (Etsy listing_id) did not populate "
                f"within {timeout:.0f}s. Live probe (2026-07-16) observed ~8 min sync lag - "
                f"this likely means Gelato's async Etsy sync is stalled or failed, not a "
                f"pipeline bug."
            )
        sleep_fn(poll_interval)


def create_or_reuse_group_product(conn, group_id: int, sizes: list, candidate: dict, static_config: dict,
                                   title: str, orientation: str = "portrait", *, store_id: str = None,
                                   api_key: str = None, poll_interval: float = 3.0,
                                   poll_timeout: float = 90.0, now=None) -> dict:
    timestamp = now if isinstance(now, str) else (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()

    live_row = conn.execute(
        "SELECT id, gelato_product_id FROM group_products WHERE group_id = ? AND status IN ('created', 'published')",
        (group_id,),
    ).fetchone()
    if live_row is not None:
        return {"group_product_id": live_row["id"], "gelato_product_id": live_row["gelato_product_id"]}

    stale_row = conn.execute(
        "SELECT id, gelato_product_id FROM group_products WHERE group_id = ? "
        "AND status IN ('mockup_failed', 'publish_failed')",
        (group_id,),
    ).fetchone()
    if stale_row is not None:
        if stale_row["gelato_product_id"]:
            gelato_client.delete_product(stale_row["gelato_product_id"], store_id=store_id, api_key=api_key)
        conn.execute(
            "UPDATE group_products SET status = 'deleted', updated_at = ? WHERE id = ?",
            (timestamp, stale_row["id"]),
        )
        conn.commit()

    templates = [config.get_template_variant(static_config, size, orientation) for size in sizes]
    template_id = templates[0]["template_id"]

    cursor = conn.execute(
        "INSERT INTO group_products (group_id, gelato_template_id, status, created_at, updated_at) "
        "VALUES (?, ?, 'pending', ?, ?)",
        (group_id, template_id, timestamp, timestamp),
    )
    conn.commit()
    group_product_id = cursor.lastrowid

    for size, template in zip(sizes, templates):
        conn.execute(
            "INSERT INTO group_product_variants "
            "(group_product_id, size, orientation, gelato_template_variant_id, price_eur, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (group_product_id, size, orientation, template["template_variant_id"],
             static_config["prices_eur"][size], timestamp),
        )
    conn.commit()

    try:
        response = gelato_client.create_product_from_template(
            template_id,
            [
                {"template_variant_id": t["template_variant_id"], "image_placeholder_name": t["image_placeholder_name"],
                 "image_url": candidate["base_image_url"]}
                for t in templates
            ],
            title, store_id=store_id, api_key=api_key,
        )
        gelato_product_id = response["id"]
        conn.execute(
            "UPDATE group_products SET gelato_product_id = ?, updated_at = ? WHERE id = ?",
            (gelato_product_id, timestamp, group_product_id),
        )
        conn.commit()

        if response.get("_dry_run"):
            images = [{"fileUrl": response.get("previewUrl") or candidate["base_image_url"], "isPrimary": True}]
        else:
            product = poll_until_ready(
                gelato_product_id, store_id=store_id, api_key=api_key,
                poll_interval=poll_interval, timeout=poll_timeout,
            )
            images = product["productImages"]
    except Exception:
        conn.execute(
            "UPDATE group_products SET status = 'mockup_failed', updated_at = ? WHERE id = ?",
            (timestamp, group_product_id),
        )
        conn.commit()
        raise

    ordered_images = sorted(images, key=lambda img: not img.get("isPrimary"))
    for order, image in enumerate(ordered_images):
        image_type = "flat_mockup" if image.get("isPrimary") else "lifestyle"
        conn.execute(
            "INSERT INTO product_images (group_product_id, image_url, alt_text, gallery_order, image_type) "
            "VALUES (?, ?, '', ?, ?)",
            (group_product_id, image.get("fileUrl"), order, image_type),
        )

    conn.execute(
        "UPDATE group_products SET status = 'created', updated_at = ? WHERE id = ?",
        (timestamp, group_product_id),
    )
    conn.commit()

    return {"group_product_id": group_product_id, "gelato_product_id": gelato_product_id}


def patch_etsy_listing(conn, group_product_id: int, group_type: str, listing_text: dict, static_config: dict, *,
                        shop_id: str = None, etsy_api_key: str = None, etsy_api_secret: str = None,
                        etsy_access_token: str = None, dry_run: bool = None, now=None) -> str:
    if dry_run is None:
        dry_run = not config.is_live_mode("ETSY")
    timestamp = now if isinstance(now, str) else (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    shop_id = shop_id or config.require_env("ETSY_SHOP_ID")

    gp_row = conn.execute(
        "SELECT gelato_product_id, etsy_listing_id FROM group_products WHERE id = ?", (group_product_id,)
    ).fetchone()
    if gp_row is None:
        raise ValueError(f"No group_products row with id {group_product_id}")

    listing_id = gp_row["etsy_listing_id"]
    if listing_id is None:
        listing_id = resolve_etsy_listing_id(gp_row["gelato_product_id"], api_key=None) if not dry_run \
            else "DRY_RUN_ETSY_LISTING_ID"
        conn.execute(
            "UPDATE group_products SET etsy_listing_id = ?, updated_at = ? WHERE id = ?",
            (listing_id, timestamp, group_product_id),
        )
        conn.commit()

    shipping_profile_id = config.get_shipping_profile_id(static_config, group_type)
    listing_data = {
        "title": listing_text["title"],
        "description": listing_text["description"],
        "tags": json.loads(listing_text["tags"]),
        "taxonomy_id": int(listing_text["taxonomy_id"]),
        "who_made": listing_text["who_made"],
        "when_made": "made_to_order",
        "is_supply": False,
        "shop_section_id": static_config["etsy_shop_section_id"],
        "production_partner_ids": json.loads(listing_text["production_partner_ids"]),
        "shipping_profile_id": shipping_profile_id,
    }
    etsy_client.update_listing(
        shop_id, listing_id, listing_data, api_key=etsy_api_key, api_secret=etsy_api_secret,
        access_token=etsy_access_token, dry_run=dry_run,
    )

    variant_rows = conn.execute(
        "SELECT size, price_eur FROM group_product_variants WHERE group_product_id = ?", (group_product_id,)
    ).fetchall()
    size_to_price = {row["size"]: row["price_eur"] for row in variant_rows}
    etsy_client.update_listing_inventory(
        shop_id, listing_id, size_to_price, api_key=etsy_api_key, api_secret=etsy_api_secret,
        access_token=etsy_access_token, dry_run=dry_run,
    )

    conn.execute(
        "UPDATE group_products SET status = 'published', updated_at = ? WHERE id = ?",
        (timestamp, group_product_id),
    )
    conn.commit()
    return listing_id
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_group_product.py -v`
Expected: PASS, all new tests green.

- [ ] **Step 5: Commit**

```bash
git add pipeline/group_product.py tests/test_group_product.py
git commit -m "feat: add group_product.py, shared group-level create-or-reuse and Etsy patch"
```

---

### Task 5: `primary_mockup.py` — delegate to `group_product.py`

**Files:**
- Modify: `pipeline/primary_mockup.py` (whole file — `poll_until_ready`/`GelatoMockupTimeoutError` move to `group_product.py`, `create_primary_mockup` delegates)
- Test: `tests/test_primary_mockup.py`

**Interfaces:**
- Consumes: `group_product.create_or_reuse_group_product`.
- Produces: same public signatures as today — `get_or_create_primary_group`, `build_mockup_title`, `create_primary_mockup(conn, candidate_id, *, static_config=None, store_id=None, api_key=None, poll_interval=3.0, poll_timeout=90.0, now=None) -> dict`, `run_primary_mockup_cycle`. `poll_until_ready`/`GelatoMockupTimeoutError` are removed from this module — anything importing `primary_mockup.poll_until_ready` must switch to `group_product.poll_until_ready` (Task 6, 7).

- [ ] **Step 1: Write the failing test**

Update the existing dry-run test(s) in `tests/test_primary_mockup.py` that assert on `group_products.size`/`price_eur` columns (search the file for `"size"` and `"price_eur"` — likely in a test named like `test_create_primary_mockup_...`). Replace column assertions:

```python
def test_create_primary_mockup_creates_group_product_with_8x12_variant(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    static_config = config.load_static_config()

    result = primary_mockup.create_primary_mockup(
        conn, candidate_id, static_config=static_config, now="2026-07-16T09:00:00",
    )

    gp_row = conn.execute(
        "SELECT * FROM group_products WHERE id = ?", (result["group_product_id"],)
    ).fetchone()
    assert gp_row["status"] == "created"
    variant_row = conn.execute(
        "SELECT size, price_eur FROM group_product_variants WHERE group_product_id = ?",
        (result["group_product_id"],),
    ).fetchone()
    assert variant_row["size"] == "8x12"
    assert variant_row["price_eur"] == static_config["prices_eur"]["8x12"]
```

Keep whatever fixture helpers (`_fresh_conn`, `_insert_candidate`) already exist in this file — don't redefine.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_primary_mockup.py -v`
Expected: FAIL — old code still inserts a `size`/`price_eur` column directly into `group_products`, which no longer exist (schema error).

- [ ] **Step 3: Rewrite `pipeline/primary_mockup.py`**

Replace the whole file:

```python
from datetime import datetime, timezone

import pipeline.config as config
import pipeline.group_product as group_product


def build_mockup_title(candidate: dict) -> str:
    return f"{candidate['niche']} - primary mockup"


def get_or_create_primary_group(conn, candidate_id: int, *, now=None) -> int:
    row = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary'",
        (candidate_id,),
    ).fetchone()
    if row is not None:
        return row["id"]

    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at)
        VALUES (?, 'primary', 'pending_generation', ?, ?)
        """,
        (candidate_id, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def create_primary_mockup(conn, candidate_id: int, *, static_config: dict = None,
                           store_id: str = None, api_key: str = None,
                           poll_interval: float = 3.0, poll_timeout: float = 90.0,
                           now=None) -> dict:
    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if row is None:
        raise ValueError(f"No candidate with id {candidate_id}")
    candidate = dict(row)

    static_config = static_config if static_config is not None else config.load_static_config()
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()

    group_id = get_or_create_primary_group(conn, candidate_id, now=now)

    result = group_product.create_or_reuse_group_product(
        conn, group_id, ["8x12"], candidate, static_config, build_mockup_title(candidate),
        store_id=store_id, api_key=api_key, poll_interval=poll_interval, poll_timeout=poll_timeout, now=now,
    )

    conn.execute(
        "UPDATE groups SET status = 'pending_review', updated_at = ? WHERE id = ?",
        (timestamp, group_id),
    )
    conn.commit()

    return {"group_id": group_id, "group_product_id": result["group_product_id"],
            "gelato_product_id": result["gelato_product_id"]}


def run_primary_mockup_cycle(conn, *, static_config: dict = None, store_id: str = None,
                              api_key: str = None, poll_interval: float = 3.0,
                              poll_timeout: float = 90.0, now=None) -> list:
    candidate_ids = [
        row["id"] for row in conn.execute(
            """
            SELECT id FROM candidates
            WHERE status = 'generating'
              AND base_image_url IS NOT NULL
              AND id NOT IN (
                SELECT g.candidate_id FROM groups g
                JOIN group_products gp ON gp.group_id = g.id
                WHERE g.group_type = 'primary'
              )
            ORDER BY id
            """
        ).fetchall()
    ]
    processed_ids = []
    for candidate_id in candidate_ids:
        try:
            create_primary_mockup(
                conn, candidate_id, static_config=static_config, store_id=store_id,
                api_key=api_key, poll_interval=poll_interval, poll_timeout=poll_timeout, now=now,
            )
        except Exception as exc:
            print(f"create_primary_mockup failed for candidate {candidate_id}: {exc}")
            continue
        processed_ids.append(candidate_id)
    return processed_ids
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_primary_mockup.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/primary_mockup.py tests/test_primary_mockup.py
git commit -m "refactor: primary_mockup.py delegates to group_product.create_or_reuse_group_product"
```

---

### Task 6: `publish_primary_group.py` — one listing for the whole primary group

**Files:**
- Modify: `pipeline/publish_primary_group.py` (remove `SIZE_TITLE_SUFFIXES`, `build_size_listing_data`, `create_group_product_row`, `create_gelato_product`, `publish_to_etsy`, `publish_group_product`; rewrite `publish_primary_group`, `handle_decision`'s `edit` branch)
- Test: `tests/test_publish_primary_group.py`

**Interfaces:**
- Consumes: `group_product.create_or_reuse_group_product`, `group_product.patch_etsy_listing`.
- Produces: `publish_primary_group(conn, candidate_id, *, static_config=None, store_id=None, gelato_api_key=None, shop_id=None, etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None, dry_run=None, now=None) -> dict` returns `{"etsy_listing_id": str}` (no longer per-size dict). Everything else (`resolve_callback`, `is_admin`, `log_telegram_event`, `record_decision`, `handle_decision`, `process_update`, `run_publish_primary_group_cycle`, telegram offset helpers) keeps its current signature.

- [ ] **Step 1: Write the failing test**

Find and update the test(s) in `tests/test_publish_primary_group.py` that currently assert `publish_primary_group` returns a per-size `results` dict (search for `results[` or `"published"` in that file). Replace with:

```python
def test_publish_primary_group_creates_one_listing_for_all_four_sizes(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    static_config = config.load_static_config()
    primary_mockup.create_primary_mockup(conn, candidate_id, static_config=static_config, now="2026-07-16T09:00:00")
    # (existing test setup already inserts listing_texts / marks the 8x12 group_products row 'created'
    #  — reuse whatever helper this file already has for that, e.g. _insert_listing_texts)

    with patch("pipeline.gelato_client.get_etsy_listing_id") as mock_resolve:
        mock_resolve.return_value = "etsy-listing-42"
        result = publish_primary_group.publish_primary_group(
            conn, candidate_id, static_config=static_config, dry_run=True, now="2026-07-16T09:20:00",
        )

    assert result["etsy_listing_id"] == "etsy-listing-42"
    gp_row = conn.execute(
        "SELECT id, status FROM group_products WHERE group_id = "
        "(SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary')",
        (candidate_id,),
    ).fetchone()
    assert gp_row["status"] == "published"
    variant_rows = conn.execute(
        "SELECT size FROM group_product_variants WHERE group_product_id = ? ORDER BY size",
        (gp_row["id"],),
    ).fetchall()
    assert [r["size"] for r in variant_rows] == ["8x12", "A1", "A2", "A3"]
```

Delete/replace any older test asserting 4 separate `group_products` rows or 4 separate Etsy drafts for the primary group — that behavior no longer exists.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_publish_primary_group.py -v`
Expected: FAIL (old code still creates 4 rows via `create_group_product_row`/schema mismatch).

- [ ] **Step 3: Rewrite the relevant parts of `pipeline/publish_primary_group.py`**

Remove lines 21-28 (`SIZE_TITLE_SUFFIXES`) and lines 73-251 (`build_size_listing_data` through `publish_group_product`) entirely. Replace with:

```python
def publish_primary_group(conn, candidate_id, *, static_config=None, store_id=None,
                           gelato_api_key=None, shop_id=None, etsy_api_key=None,
                           etsy_api_secret=None, etsy_access_token=None, dry_run=None, now=None) -> dict:
    static_config = static_config if static_config is not None else config.load_static_config()
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()

    candidate_row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if candidate_row is None:
        raise ValueError(f"No candidate with id {candidate_id}")
    candidate = dict(candidate_row)

    group_row = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary'", (candidate_id,)
    ).fetchone()
    if group_row is None:
        raise ValueError(f"No primary group for candidate {candidate_id}")
    group_id = group_row["id"]

    listing_text_row = conn.execute(
        "SELECT * FROM listing_texts WHERE candidate_id = ?", (candidate_id,)
    ).fetchone()
    if listing_text_row is None:
        raise ValueError(f"No listing_texts row for candidate {candidate_id}")
    listing_text = dict(listing_text_row)

    sizes = static_config["aspect_ratio_groups"]["primary"]

    def attempt():
        result = group_product.create_or_reuse_group_product(
            conn, group_id, sizes, candidate, static_config, listing_text["title"],
            store_id=store_id, api_key=gelato_api_key, now=now,
        )
        return group_product.patch_etsy_listing(
            conn, result["group_product_id"], "primary", listing_text, static_config,
            shop_id=shop_id, etsy_api_key=etsy_api_key, etsy_api_secret=etsy_api_secret,
            etsy_access_token=etsy_access_token, dry_run=dry_run, now=now,
        )

    try:
        try:
            etsy_listing_id = attempt()
        except Exception:
            etsy_listing_id = attempt()
    except Exception:
        conn.execute(
            "UPDATE groups SET status = 'publish_failed', updated_at = ? WHERE id = ?",
            (timestamp, group_id),
        )
        conn.commit()
        raise

    conn.execute(
        "UPDATE groups SET status = 'approved_published', updated_at = ? WHERE id = ?",
        (timestamp, group_id),
    )
    conn.execute(
        "UPDATE candidates SET status = 'completed', updated_at = ? WHERE id = ?",
        (timestamp, candidate_id),
    )
    conn.commit()

    return {"etsy_listing_id": etsy_listing_id}
```

Add `import pipeline.group_product as group_product` to the imports at the top of the file (alongside the existing `import pipeline.gelato_client as gelato_client` etc — keep `gelato_client` import only if still used elsewhere in the file; check before removing).

In `handle_decision`'s `"approve"` branch (former lines 348-356), update the return shape:

```python
    if action == "approve":
        record_decision(conn, group_id, "approved", decision_notes, now=now)
        result = publish_primary_group(
            conn, candidate_id, static_config=static_config, store_id=store_id,
            gelato_api_key=gelato_api_key, shop_id=shop_id, etsy_api_key=etsy_api_key,
            etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
            dry_run=dry_run, now=now,
        )
        return {"action": "approve", **result}
```

In `handle_decision`'s `"edit"` branch (former lines 358-386), the lookup for the row to discard no longer filters by `size = '8x12'` (the group_products row is group-level now):

```python
        old_gp_row = conn.execute(
            "SELECT id FROM group_products WHERE group_id = ? AND status = 'created'",
            (group_id,),
        ).fetchone()
```

(rest of the `edit` branch unchanged).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_publish_primary_group.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/publish_primary_group.py tests/test_publish_primary_group.py
git commit -m "feat: publish_primary_group creates one Gelato product + one Etsy listing for all 4 primary sizes"
```

---

### Task 7: `group_mockup.py` — delegate 5x7/10x24 creation to `group_product.py`

**Files:**
- Modify: `pipeline/group_mockup.py` (whole file)
- Test: `tests/test_group_mockup.py`

**Interfaces:**
- Consumes: `group_product.create_or_reuse_group_product`.
- Produces: same public signatures — `get_or_create_group`, `create_group_mockup(conn, candidate_id, group_type, *, static_config=None, store_id=None, api_key=None, poll_interval=3.0, poll_timeout=90.0, now=None) -> dict | None`, `GROUP_TYPES`, `run_group_mockup_cycle`. `_group_size` is replaced by `_group_sizes` returning the full list (ready for a future multi-size 5x7/10x24 group without another rewrite, per CLAUDE.md's "5x7 or 10x24 group" wording never promising exactly one size).

- [ ] **Step 1: Write the failing test**

Update the test(s) in `tests/test_group_mockup.py` that assert on `group_products.size`/`price_eur` for the created row (search for `"size"`/`"price_eur"`):

```python
def test_create_group_mockup_creates_group_product_with_group_variant(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_group(conn, candidate_id, status="approved_published")
    static_config = config.load_static_config()

    result = group_mockup.create_group_mockup(
        conn, candidate_id, "5x7", static_config=static_config, now="2026-07-16T09:00:00",
    )

    variant_row = conn.execute(
        "SELECT size, price_eur FROM group_product_variants WHERE group_product_id = ?",
        (result["group_product_id"],),
    ).fetchone()
    assert variant_row["size"] == "5x7"
    assert variant_row["price_eur"] == static_config["prices_eur"]["5x7"]
```

Keep whatever `_fresh_conn`/`_insert_candidate`/`_insert_primary_group`-style fixtures this file already has.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_group_mockup.py -v`
Expected: FAIL (old code inserts into the now-removed `size`/`price_eur` columns on `group_products`).

- [ ] **Step 3: Rewrite `pipeline/group_mockup.py`**

Replace the whole file:

```python
import pipeline.config as config
import pipeline.group_product as group_product


def get_or_create_group(conn, candidate_id: int, group_type: str, *, now=None) -> int:
    from datetime import datetime, timezone
    row = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = ?",
        (candidate_id, group_type),
    ).fetchone()
    if row is not None:
        return row["id"]

    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at)
        VALUES (?, ?, 'pending_generation', ?, ?)
        """,
        (candidate_id, group_type, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _group_sizes(static_config: dict, group_type: str) -> list:
    return static_config["aspect_ratio_groups"][group_type]


def create_group_mockup(conn, candidate_id: int, group_type: str, *, static_config: dict = None,
                         store_id: str = None, api_key: str = None,
                         poll_interval: float = 3.0, poll_timeout: float = 90.0,
                         now=None) -> dict | None:
    candidate_row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if candidate_row is None:
        raise ValueError(f"No candidate with id {candidate_id}")
    candidate = dict(candidate_row)

    static_config = static_config if static_config is not None else config.load_static_config()

    group_id = get_or_create_group(conn, candidate_id, group_type, now=now)

    group_status_row = conn.execute(
        "SELECT status FROM groups WHERE id = ?", (group_id,)
    ).fetchone()
    if group_status_row["status"] in ("failed_abandoned", "rejected"):
        return None

    live_row = conn.execute(
        "SELECT id FROM group_products WHERE group_id = ? AND status IN ('created', 'published')",
        (group_id,),
    ).fetchone()
    if live_row is not None:
        return None

    sizes = _group_sizes(static_config, group_type)

    def attempt():
        return group_product.create_or_reuse_group_product(
            conn, group_id, sizes, candidate, static_config, f"{candidate['niche']} - {group_type} mockup",
            store_id=store_id, api_key=api_key, poll_interval=poll_interval, poll_timeout=poll_timeout, now=now,
        )

    try:
        result = attempt()
    except Exception:
        result = attempt()

    from datetime import datetime, timezone
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    conn.execute(
        "UPDATE groups SET status = 'pending_review', updated_at = ? WHERE id = ?",
        (timestamp, group_id),
    )
    conn.commit()

    return {"group_id": group_id, "group_product_id": result["group_product_id"],
            "gelato_product_id": result["gelato_product_id"]}


GROUP_TYPES = ("5x7", "10x24")


def run_group_mockup_cycle(conn, *, static_config: dict = None, store_id: str = None,
                            api_key: str = None, poll_interval: float = 3.0,
                            poll_timeout: float = 90.0, now=None) -> list:
    static_config = static_config if static_config is not None else config.load_static_config()

    candidate_ids = [
        row["id"] for row in conn.execute(
            """
            SELECT c.id FROM candidates c
            JOIN groups g ON g.candidate_id = c.id AND g.group_type = 'primary'
                          AND g.status = 'approved_published'
            ORDER BY c.id
            """
        ).fetchall()
    ]

    processed = []
    for candidate_id in candidate_ids:
        for group_type in GROUP_TYPES:
            try:
                result = create_group_mockup(
                    conn, candidate_id, group_type, static_config=static_config,
                    store_id=store_id, api_key=api_key, poll_interval=poll_interval,
                    poll_timeout=poll_timeout, now=now,
                )
            except Exception as exc:
                print(f"create_group_mockup failed for candidate {candidate_id} "
                      f"group_type {group_type}: {exc}")
                continue
            if result is not None:
                processed.append({
                    "candidate_id": candidate_id,
                    "group_type": group_type,
                    "gelato_product_id": result["gelato_product_id"],
                })
    return processed
```

(`datetime`/`timezone` imports are done inline in two spots above to match the plan's exact code — during implementation, move both to a single top-of-file `from datetime import datetime, timezone` import instead, which is the obviously cleaner form; the duplication above is only an artifact of how this snippet was assembled.)

**Note on the retry semantics change:** the old code had a bespoke double-`attempt()` try/except identical to what `group_product.create_or_reuse_group_product` doesn't itself retry — `create_or_reuse_group_product` is called twice here (mirroring the old file's own retry-once behavior) rather than retried inside `group_product.py`, so a first-attempt failure still gets exactly one retry before `create_group_mockup` propagates the exception to `run_group_mockup_cycle`'s catch-and-log.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_group_mockup.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/group_mockup.py tests/test_group_mockup.py
git commit -m "refactor: group_mockup.py delegates to group_product.create_or_reuse_group_product"
```

---

### Task 8: `publish_group.py` — patch instead of per-size create-draft

**Files:**
- Modify: `pipeline/publish_group.py` (the `"approve"` branch of `handle_decision`)
- Test: `tests/test_publish_group.py`

**Interfaces:**
- Consumes: `group_product.patch_etsy_listing`.
- Produces: same signatures — `get_live_group_product` unchanged (already queries by `group_id`+status only, no `size` filter, so it needs no change), `handle_decision` unchanged signature, `"approve"` result becomes `{"action": "approve", "etsy_listing_id": str}` (was `"listing_id"` — rename to match `group_product.patch_etsy_listing`'s naming, and update every caller/test).

- [ ] **Step 1: Write the failing test**

Update the test(s) in `tests/test_publish_group.py` asserting on `handle_decision`'s approve return (search for `"listing_id"`):

```python
def test_handle_decision_approve_patches_existing_etsy_listing(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_group(conn, candidate_id, status="approved_published")
    group_id = _insert_group(conn, candidate_id, "5x7", status="pending_review")
    static_config = config.load_static_config()
    group_mockup.create_group_mockup(conn, candidate_id, "5x7", static_config=static_config, now="2026-07-16T09:00:00")
    # (existing test setup already inserts listing_texts — reuse that helper)

    with patch("pipeline.gelato_client.get_etsy_listing_id") as mock_resolve:
        mock_resolve.return_value = "etsy-listing-99"
        result = publish_group.handle_decision(
            conn, candidate_id, group_id, "approve", static_config=static_config,
            dry_run=True, now="2026-07-16T09:10:00",
        )

    assert result == {"action": "approve", "etsy_listing_id": "etsy-listing-99"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_publish_group.py -v`
Expected: FAIL (old code calls `publish_primary_group.publish_group_product`, which was deleted in Task 6).

- [ ] **Step 3: Rewrite the `"approve"` branch**

Replace `pipeline/publish_group.py:25-54`:

```python
    if action == "approve":
        publish_primary_group.record_decision(conn, group_id, "approved", decision_notes, now=now)
        static_config = static_config if static_config is not None else config.load_static_config()

        group_product_row = get_live_group_product(conn, group_id)
        candidate_id_row = conn.execute(
            "SELECT candidate_id, group_type FROM groups WHERE id = ?", (group_id,)
        ).fetchone()
        group_type = candidate_id_row["group_type"]
        listing_text = dict(
            conn.execute("SELECT * FROM listing_texts WHERE candidate_id = ?", (candidate_id,)).fetchone()
        )

        try:
            etsy_listing_id = group_product.patch_etsy_listing(
                conn, group_product_row["id"], group_type, listing_text, static_config,
                shop_id=shop_id, etsy_api_key=etsy_api_key, etsy_api_secret=etsy_api_secret,
                etsy_access_token=etsy_access_token, dry_run=dry_run, now=now,
            )
        except Exception:
            conn.execute(
                "UPDATE groups SET status = 'publish_failed', updated_at = ? WHERE id = ?",
                (timestamp, group_id),
            )
            conn.commit()
            raise

        conn.execute(
            "UPDATE groups SET status = 'approved_published', updated_at = ? WHERE id = ?",
            (timestamp, group_id),
        )
        conn.commit()
        return {"action": "approve", "etsy_listing_id": etsy_listing_id}
```

Add `import pipeline.group_product as group_product` to the file's imports.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_publish_group.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/publish_group.py tests/test_publish_group.py
git commit -m "feat: publish_group.py patches the group's existing Etsy listing instead of creating a new draft"
```

---

### Task 9: Cascade-delete `group_product_variants` in `critic_pass.py` and `cleanup.py`

**Files:**
- Modify: `pipeline/critic_pass.py:104-114` (`discard_superseded_attempt`)
- Modify: `pipeline/cleanup.py` (wherever `product_images`/`group_products` are deleted together — the two spots the earlier grep found, roughly lines 65-77)
- Test: `tests/test_group_critic_pass.py` (covers `discard_superseded_attempt` reuse) and `tests/test_cleanup.py` if it exists (check `Glob tests/test_cleanup*.py` first; if no such file, add cases to whichever cleanup test file exists)

**Interfaces:** no signature changes — same functions, just delete one more table's rows.

- [ ] **Step 1: Write the failing test**

Add near existing `discard_superseded_attempt` tests (find the test file that covers `pipeline/critic_pass.py` — likely `tests/test_critic_pass.py`; `Glob` to confirm the exact name first):

```python
def test_discard_superseded_attempt_also_deletes_variant_rows(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_primary_group(conn, candidate_id)
    timestamp = "2026-07-16T09:00:00"
    conn.execute(
        "INSERT INTO group_products (group_id, gelato_template_id, gelato_product_id, status, created_at, updated_at) "
        "VALUES (?, 'tmpl', 'gelato-1', 'created', ?, ?)", (group_id, timestamp, timestamp),
    )
    group_product_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    conn.execute(
        "INSERT INTO group_product_variants (group_product_id, size, orientation, gelato_template_variant_id, price_eur, created_at) "
        "VALUES (?, '8x12', 'portrait', 'var1', 24.0, ?)", (group_product_id, timestamp),
    )
    conn.commit()

    with patch("pipeline.gelato_client.delete_product"):
        critic_pass.discard_superseded_attempt(conn, group_product_id)

    remaining = conn.execute(
        "SELECT COUNT(*) AS n FROM group_product_variants WHERE group_product_id = ?", (group_product_id,)
    ).fetchone()
    assert remaining["n"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_critic_pass.py -v -k discard_superseded_attempt_also_deletes_variant_rows`
Expected: FAIL — the variant row survives (foreign-key row deletion isn't automatic; SQLite doesn't cascade by default and this schema doesn't declare `ON DELETE CASCADE`).

- [ ] **Step 3: Update `discard_superseded_attempt`**

Replace `pipeline/critic_pass.py:104-114`:

```python
def discard_superseded_attempt(conn, group_product_id: int, *, store_id: str = None, api_key: str = None) -> None:
    row = conn.execute(
        "SELECT gelato_product_id FROM group_products WHERE id = ?", (group_product_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"No group_products row with id {group_product_id}")
    if row["gelato_product_id"]:
        gelato_client.delete_product(row["gelato_product_id"], store_id=store_id, api_key=api_key)
    conn.execute("DELETE FROM group_product_variants WHERE group_product_id = ?", (group_product_id,))
    conn.execute("DELETE FROM product_images WHERE group_product_id = ?", (group_product_id,))
    conn.execute("DELETE FROM group_products WHERE id = ?", (group_product_id,))
    conn.commit()
```

Then update `pipeline/cleanup.py`: at each spot deleting from `product_images`/`group_products` for orphan cleanup (the two blocks the earlier grep found around lines 65-77), add a matching `DELETE FROM group_product_variants WHERE group_product_id IN (...)` using the same subquery shape as the neighboring `product_images` delete, inserted immediately before it.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_critic_pass.py tests/test_cleanup.py -v`
Expected: PASS (adjust the second file name if `Glob` in Step 1 found a different actual filename for cleanup tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline/critic_pass.py pipeline/cleanup.py tests/
git commit -m "fix: cascade-delete group_product_variants alongside product_images/group_products"
```

---

### Task 10: `digest.py` / `group_digest.py` — render per-size prices

**Files:**
- Modify: `pipeline/digest.py:8-20` (the query building `price_eur`) and `build_digest_message_text` (line 48)
- Modify: `pipeline/group_digest.py:11-20` (same) and `build_group_digest_message_text` (line 39)
- Test: `tests/test_digest.py`, `tests/test_group_digest.py`

**Interfaces:**
- Produces: `build_digest_message_text(candidate_id, group_id, listing_text, variants) -> str` where `variants` is `list[{"size": str, "price_eur": float}]` sorted by size (was `price_eur: float`).
- Produces: `build_group_digest_message_text(candidate_id, group_id, group_type, listing_text, variants) -> str` — same `variants` shape.

- [ ] **Step 1: Write the failing test**

In `tests/test_digest.py`, update the test(s) covering `build_digest_message_text` (search for `"Price: €"`):

```python
def test_build_digest_message_text_lists_every_size_and_price():
    text = digest.build_digest_message_text(
        7, 42, {"title": "Monstera Line Art", "description": "desc"},
        [{"size": "8x12", "price_eur": 24.0}, {"size": "A3", "price_eur": 35.0},
         {"size": "A2", "price_eur": 39.0}, {"size": "A1", "price_eur": 49.0}],
    )
    assert "8x12 €24.0" in text
    assert "A3 €35.0" in text
    assert "A1 €49.0" in text
```

Mirror the same change in `tests/test_group_digest.py` for `build_group_digest_message_text`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_digest.py tests/test_group_digest.py -v`
Expected: FAIL (`build_digest_message_text` still takes a single `price_eur: float`).

- [ ] **Step 3: Update both files**

In `pipeline/digest.py`, replace the query at lines 8-20 to fetch variants instead of a single price, and update `build_digest_message_text`:

```python
def get_review_group(conn, candidate_id: int) -> dict:
    group_row = conn.execute(
        """
        SELECT g.id AS group_id, gp.id AS group_product_id
        FROM groups g
        JOIN group_products gp ON gp.group_id = g.id AND gp.status = 'created'
        WHERE g.candidate_id = ? AND g.group_type = 'primary'
        """,
        (candidate_id,),
    ).fetchone()
    if group_row is None:
        raise ValueError(f"No live primary group_product for candidate {candidate_id}")
    variant_rows = conn.execute(
        "SELECT size, price_eur FROM group_product_variants WHERE group_product_id = ? ORDER BY size",
        (group_row["group_product_id"],),
    ).fetchall()
    return {"group_id": group_row["group_id"],
            "variants": [{"size": r["size"], "price_eur": r["price_eur"]} for r in variant_rows]}
```

(Keep the function's actual current name from the file — the earlier grep showed the query inline in whatever function currently builds this dict; adapt the surrounding function name/shape to match what's actually there, only the SELECT and return shape need to change.)

```python
def build_digest_message_text(candidate_id: int, group_id: int, listing_text: dict, variants: list) -> str:
    price_lines = " · ".join(f"{v['size']} €{v['price_eur']}" for v in variants)
    return (
        f"Candidate #{candidate_id} - Primary group (#{group_id})\n"
        f"{listing_text['title']}\n\n"
        f"{listing_text['description']}\n\n"
        f"Sizes: {price_lines}"
    )
```

(Match the existing message format exactly except swapping the single `Price: €{price_eur}` line for the `Sizes: {price_lines}` line — check the current full template around line 48-55 first and preserve every other line unchanged.)

Update the call site (former line 78) to pass `group["variants"]` instead of `group["price_eur"]`.

Apply the identical shape of change to `pipeline/group_digest.py` (`build_group_digest_message_text`, its query at lines 11-20, and the call site at line 63).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_digest.py tests/test_group_digest.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/digest.py pipeline/group_digest.py tests/test_digest.py tests/test_group_digest.py
git commit -m "feat: digest messages list every variant's size and price, not one candidate price"
```

---

### Task 11: `compliance_draft.py` — drop the per-size title-suffix headroom

**Files:**
- Modify: `pipeline/compliance_draft.py` (the `MAX_TITLE_LENGTH` headroom subtraction and its comment, around lines 18-28)
- Test: `tests/test_compliance_draft.py`

**Interfaces:** no signature change — `validate_listing_text`/title-length constant just uses Etsy's real 140-char max directly instead of `140 - longest_suffix_length`, since titles no longer get a per-size suffix appended anywhere (Task 6 removed `SIZE_TITLE_SUFFIXES`).

- [ ] **Step 1: Write the failing test**

In `tests/test_compliance_draft.py`, find the test asserting the headroom-reduced max length (search for the literal number that's `140` minus the longest suffix, e.g. `140 - len(" - 10x24 Panoramic Print")`), and update it to assert the full 140-char Etsy limit is now allowed:

```python
def test_title_up_to_full_etsy_max_length_is_valid_no_size_suffix_headroom():
    title = "x" * 140
    compliance_draft.validate_listing_text(title, ["tag1"])  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_compliance_draft.py -v -k full_etsy_max_length`
Expected: FAIL — old code still rejects a 140-char title because of the reserved suffix headroom.

- [ ] **Step 3: Update `pipeline/compliance_draft.py`**

Read the current headroom comment/constant at lines 18-28 first (exact current code), then remove the subtraction so `MAX_TITLE_LENGTH` (or equivalent) is Etsy's real 140-char limit with no reserved headroom, and delete the now-stale comment referencing `SIZE_TITLE_SUFFIXES` (that dict no longer exists after Task 6).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_compliance_draft.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/compliance_draft.py tests/test_compliance_draft.py
git commit -m "fix: title validation uses Etsy's full 140-char limit, no per-size suffix headroom"
```

---

### Task 12: Full regression pass

**Files:** none new — this task is verification only.

- [ ] **Step 1: Run the entire suite**

Run: `python -m pytest tests/ -v`

- [ ] **Step 2: Fix any remaining breakage**

Grep the whole repo one more time for anything still assuming the old per-size `group_products` shape:

Run: `grep -rn "group_products.*size\|size.*group_products\|SIZE_TITLE_SUFFIXES\|publish_group_product\|create_gelato_product\|build_size_listing_data\|create_draft_listing" pipeline/ tests/`

Fix every hit (`create_draft_listing` should only appear in `etsy_client.py`'s definition and `test_etsy_client.py`'s tests of it — zero callers elsewhere per the Global Constraints).

- [ ] **Step 3: Confirm final green state**

Run: `python -m pytest tests/ -v`
Expected: PASS, full suite green, matching or exceeding the pre-migration test count (this plan adds tests in Tasks 1-11 and removes none of substance — a lower total would mean something was silently deleted rather than migrated).

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "test: full regression pass after variant-listing migration"
```

---

## Self-Review

**Spec coverage:** SPEC v4.11's "one Etsy listing per aspect-ratio group, sizes are variants" → Tasks 1, 4, 6, 8. "Gelato pushes, we patch" (resolve `listing_id`, PATCH via `updateListing`/`updateListingInventory`, never `create_draft_listing`) → Tasks 2, 3, 4, 6, 8. "Gelato create must be idempotic, one shared create-or-reuse helper" → Task 4 (`create_or_reuse_group_product` used by Tasks 5, 6, 7). Data storage "one row per aspect-ratio group... one Gelato product + one Etsy listing" → Task 1. Items 7/8/10/11 from the live-test fix plan (title/description/tags/section/partner missing) → Task 4's `patch_etsy_listing` field set. Item 9 (AI-tools field) and orientation/digital-download are explicitly out of scope per the earlier decision in this session — not covered here, correctly.

**Placeholder scan:** no TBD/TODO/"add error handling" left in any step; every step has real code or a concrete grep/pytest command.

**Type consistency:** `create_or_reuse_group_product` returns `{"group_product_id", "gelato_product_id"}` consistently used in Tasks 5, 6, 7. `patch_etsy_listing` returns the listing id string, consumed identically in Tasks 6 and 8. `variants` list-of-dicts shape (`{"size", "price_eur"}`) matches between Task 4's `group_product_variants` reads and Task 10's digest renderers.
