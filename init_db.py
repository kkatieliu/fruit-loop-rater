import sqlite3

connection = sqlite3.connect("fruitloop.db")   # creates the file if it doesn't exist

connection.executescript("""
    CREATE TABLE IF NOT EXISTS fruits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        emoji TEXT
    );

    INSERT OR IGNORE INTO fruits (name, emoji) VALUES
        ('Strawberry', '🍓'),
        ('Mango', '🥭'),
        ('Lychee', '🫐'),
        ('Watermelon', '🍉');

    CREATE TABLE IF NOT EXISTS ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fruit_id INTEGER NOT NULL REFERENCES fruits(id),
        score INTEGER NOT NULL CHECK (score BETWEEN 1 AND 5),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
"""

)

connection.commit()
connection.close()
print("Database created with starter fruits!")