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
  status TEXT NOT NULL CHECK(status IN (
    'pending','generating','primary_review','failed','abandoned','completed'
  )),
  failed_reason TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS listing_texts (
  id INTEGER PRIMARY KEY,
  candidate_id INTEGER NOT NULL REFERENCES candidates(id),
  title TEXT NOT NULL,
  tags TEXT NOT NULL,
  description TEXT NOT NULL,
  disclosure_text TEXT NOT NULL,
  who_made TEXT NOT NULL,
  production_partner_ids TEXT NOT NULL,
  taxonomy_id TEXT NOT NULL,
  shipping_profile_id TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS groups (
  id INTEGER PRIMARY KEY,
  candidate_id INTEGER NOT NULL REFERENCES candidates(id),
  group_type TEXT NOT NULL CHECK(group_type IN ('primary','5x7','10x24')),
  decision TEXT CHECK(decision IN ('approved','edited','rejected')),
  decision_notes TEXT,
  decided_at TEXT,
  status TEXT NOT NULL CHECK(status IN (
    'pending_generation','pending_review','approved_published','rejected','failed_abandoned'
  )),
  failed_reason TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(candidate_id, group_type)
);

CREATE TABLE IF NOT EXISTS critic_pass_attempts (
  id INTEGER PRIMARY KEY,
  group_id INTEGER NOT NULL REFERENCES groups(id),
  attempt_number INTEGER NOT NULL CHECK(attempt_number BETWEEN 1 AND 3),
  passed INTEGER NOT NULL,
  failure_reason TEXT,
  correction_notes TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(group_id, attempt_number)
);

CREATE TABLE IF NOT EXISTS group_products (
  id INTEGER PRIMARY KEY,
  group_id INTEGER NOT NULL REFERENCES groups(id),
  size TEXT NOT NULL CHECK(size IN ('5x7','8x12','A3','A2','10x24','A1')),
  orientation TEXT NOT NULL CHECK(orientation IN ('portrait','landscape')),
  gelato_template_id TEXT NOT NULL,
  gelato_product_id TEXT,
  etsy_listing_id TEXT,
  price_eur REAL NOT NULL,
  title TEXT,
  status TEXT NOT NULL CHECK(status IN (
    'pending','created','publish_failed','published','deleted'
  )),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS product_images (
  id INTEGER PRIMARY KEY,
  group_product_id INTEGER NOT NULL REFERENCES group_products(id),
  image_url TEXT NOT NULL,
  alt_text TEXT NOT NULL,
  gallery_order INTEGER NOT NULL,
  image_type TEXT NOT NULL CHECK(image_type IN ('flat_mockup','lifestyle'))
);

CREATE TABLE IF NOT EXISTS group_messages (
  id INTEGER PRIMARY KEY,
  group_id INTEGER NOT NULL REFERENCES groups(id),
  telegram_message_id INTEGER NOT NULL,
  chat_id TEXT NOT NULL,
  sent_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS telegram_events_log (
  id INTEGER PRIMARY KEY,
  received_at TEXT NOT NULL,
  telegram_user_id TEXT NOT NULL,
  raw_payload TEXT NOT NULL,
  accepted INTEGER NOT NULL,
  action_taken TEXT
);

CREATE TABLE IF NOT EXISTS listing_metrics_snapshots (
  id INTEGER PRIMARY KEY,
  group_product_id INTEGER NOT NULL REFERENCES group_products(id),
  snapshot_date TEXT NOT NULL,
  views INTEGER NOT NULL,
  num_favorers INTEGER NOT NULL,
  orders_count INTEGER NOT NULL
);
