import sqlite3

connection = sqlite3.connect("fruitloop.db")   # creates the file if it doesn't exist

## the unique in the ratings table ensures that a user can only rate a fruit once
connection.executescript("""
    CREATE TABLE IF NOT EXISTS fruits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        emoji TEXT
    );

    INSERT OR IGNORE INTO fruits (name, emoji) VALUES
        ('Watermelon', '🍉'),
        ('Strawberries', '🍓'),
        ('Banana', '🍌'),
        ('Tomato', '🍅'),
        ('Ogrange', '🍊'),
        ('Kiwi', '🥝');

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
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
        overall INTEGER NOT NULL CHECK (overall BETWEEN 1 AND 10),
        purchase_date DATE NOT NULL,
        consumed_date DATE NOT NULL CHECK (consumed_date >= purchase_date),
        week_start DATE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (user_id, fruit_id, location_id, week_start)
    );
""")

connection.commit()
connection.close()
print("Database created with starter fruits!")