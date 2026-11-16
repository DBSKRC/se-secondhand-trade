PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    account TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK (role IN ('member', 'admin')),
    salt TEXT NOT NULL,
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY,
    seller_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    condition TEXT NOT NULL,
    price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
    state TEXT NOT NULL CHECK (state IN (
        'draft', 'review', 'rejected', 'published', 'reserved',
        'trading', 'completed', 'withdrawn', 'frozen'
    )),
    version INTEGER NOT NULL DEFAULT 1,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS item_images (
    item_id INTEGER NOT NULL REFERENCES items(id),
    position INTEGER NOT NULL,
    filename TEXT NOT NULL,
    contents BLOB NOT NULL,
    PRIMARY KEY (item_id, position)
);
CREATE TABLE IF NOT EXISTS reservations (
    id INTEGER PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES items(id),
    buyer_id INTEGER NOT NULL REFERENCES users(id),
    price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
    state TEXT NOT NULL CHECK (state IN (
        'pending', 'cancelled', 'rejected', 'trading',
        'delivered', 'completed', 'disputed'
    )),
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    closed_reason TEXT NOT NULL DEFAULT '',
    completed_at INTEGER
);
CREATE UNIQUE INDEX IF NOT EXISTS reservation_one_active
ON reservations(item_id)
WHERE state IN ('pending', 'trading', 'delivered', 'disputed');
CREATE INDEX IF NOT EXISTS reservation_expiry
ON reservations(state, expires_at);
CREATE INDEX IF NOT EXISTS reservation_buyer ON reservations(buyer_id, id);
CREATE INDEX IF NOT EXISTS item_public ON items(state, category, price_cents);
CREATE INDEX IF NOT EXISTS item_seller ON items(seller_id, state);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES items(id),
    admin_id INTEGER NOT NULL REFERENCES users(id),
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES items(id),
    reporter_id INTEGER NOT NULL REFERENCES users(id),
    reason TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    admin_id INTEGER REFERENCES users(id),
    result TEXT,
    handled_at INTEGER
);
CREATE TABLE IF NOT EXISTS disputes (
    id INTEGER PRIMARY KEY,
    reservation_id INTEGER NOT NULL UNIQUE REFERENCES reservations(id),
    reason TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS dispute_notes (
    id INTEGER PRIMARY KEY,
    dispute_id INTEGER NOT NULL REFERENCES disputes(id),
    admin_id INTEGER NOT NULL REFERENCES users(id),
    body TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY,
    actor_id INTEGER REFERENCES users(id),
    action TEXT NOT NULL,
    entity TEXT NOT NULL,
    entity_id INTEGER,
    before_state TEXT,
    after_state TEXT,
    outcome TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_search ON audit(created_at, actor_id, action);
CREATE TABLE IF NOT EXISTS requests (
    actor_id INTEGER NOT NULL REFERENCES users(id),
    operation TEXT NOT NULL,
    request_key TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    response TEXT NOT NULL,
    PRIMARY KEY (actor_id, operation, request_key)
);
