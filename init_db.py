import os
import sqlite3

DB_PATH = os.environ.get("DATABASE_PATH", "fruitloop.db")

connection = sqlite3.connect(DB_PATH)
## a user can rate a fruit at a Costco as many times as they want per week;
## their contribution to any average is their own ratings averaged together first
connection.executescript("""
    CREATE TABLE IF NOT EXISTS fruits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        emoji TEXT
    );

    -- Runs before the seed INSERT below: renames an already-seeded
    -- 'Strawberries' row to 'Strawberry' first, so the INSERT OR IGNORE's
    -- 'Strawberry' row correctly gets skipped as a duplicate instead of
    -- being created alongside the old row under its old name.
    UPDATE fruits SET name = 'Strawberry' WHERE name = 'Strawberries';

    INSERT OR IGNORE INTO fruits (name, emoji) VALUES
        ('Watermelon', '🍉'),
        ('Strawberry', '🍓'),
        ('Banana', '🍌'),
        ('Tomato', '🍅'),
        ('Ogrange', '🍊'),
        ('Kiwi', '🥝'),
        ('Pear', '🍐'),
        ('Pineapple', '🍍');

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        email TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nickname TEXT NOT NULL UNIQUE,
        address TEXT NOT NULL
    );

    INSERT OR IGNORE INTO locations (nickname, address) VALUES
        ('Brighton', '3550 Brighton Ave, Burnaby, BC V5A 4W3, Canada'),
        ('Still Creek', '4500 Still Creek Dr, Burnaby, BC V5C 0E5, Canada'),
        ('Costco Downtown', '605 Expo Blvd, Vancouver, BC V6B 1V4, Canada');

    CREATE TABLE IF NOT EXISTS ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id),
        fruit_id INTEGER NOT NULL REFERENCES fruits(id),
        location_id INTEGER NOT NULL REFERENCES locations(id),
        sweetness INTEGER NOT NULL CHECK (sweetness BETWEEN 1 AND 10),
        juiciness INTEGER NOT NULL CHECK (juiciness BETWEEN 1 AND 10),
        firmness INTEGER NOT NULL CHECK (firmness BETWEEN 1 AND 10),
        overall INTEGER CHECK (overall BETWEEN 1 AND 10),
        purchase_date DATE NOT NULL,
        consumed_date DATE NOT NULL CHECK (consumed_date >= purchase_date),
        week_start DATE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
""")

# CREATE TABLE IF NOT EXISTS won't add columns to a table that already
# exists, so ratings tables created before "overall" was added need an
# explicit migration. Nullable, so pre-existing rows are left as NULL
# rather than failing.
existing_columns = {row[1] for row in connection.execute("PRAGMA table_info(ratings)")}
if "overall" not in existing_columns:
    connection.execute("ALTER TABLE ratings ADD COLUMN overall INTEGER CHECK (overall BETWEEN 1 AND 10)")
    print("Migrated: added 'overall' column to ratings")

# Older ratings tables enforced one rating per user/fruit/location/week with
# a UNIQUE constraint. SQLite can't drop an inline constraint via ALTER
# TABLE, so a table that still has it gets rebuilt without it (all rows are
# preserved). Fresh databases from the executescript above never had it.
existing_sql = connection.execute(
    "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'ratings'"
).fetchone()[0]
if "UNIQUE (user_id, fruit_id, location_id, week_start)" in existing_sql:
    print("Migrating: dropping one-rating-per-week UNIQUE constraint (rebuilding ratings table)")
    connection.execute("PRAGMA foreign_keys = OFF")
    connection.execute("""
        CREATE TABLE ratings_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            fruit_id INTEGER NOT NULL REFERENCES fruits(id),
            location_id INTEGER NOT NULL REFERENCES locations(id),
            sweetness INTEGER NOT NULL CHECK (sweetness BETWEEN 1 AND 10),
            juiciness INTEGER NOT NULL CHECK (juiciness BETWEEN 1 AND 10),
            firmness INTEGER NOT NULL CHECK (firmness BETWEEN 1 AND 10),
            overall INTEGER CHECK (overall BETWEEN 1 AND 10),
            purchase_date DATE NOT NULL,
            consumed_date DATE NOT NULL CHECK (consumed_date >= purchase_date),
            week_start DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    connection.execute("""
        INSERT INTO ratings_new
            (id, user_id, fruit_id, location_id, sweetness, juiciness, firmness,
             overall, purchase_date, consumed_date, week_start, created_at)
        SELECT id, user_id, fruit_id, location_id, sweetness, juiciness, firmness,
               overall, purchase_date, consumed_date, week_start, created_at
        FROM ratings
    """)
    connection.execute("DROP TABLE ratings")
    connection.execute("ALTER TABLE ratings_new RENAME TO ratings")
    connection.execute("PRAGMA foreign_keys = ON")
    print("Migrated: ratings table rebuilt without UNIQUE constraint")

connection.commit()
connection.close()
print("Database created with starter fruits!")