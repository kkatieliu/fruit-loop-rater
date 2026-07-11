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
        ('Strawberry', '🍓'),
        ('Mango', '🥭'),
        ('Lychee', '🫐'),
        ('Watermelon', '🍉');
    
    CREATE TABLE IF NOT EXISTS ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id),
        fruit_id INTEGER NOT NULL REFERENCES fruits(id),
        score INTEGER NOT NULL CHECK (score BETWEEN 1 AND 5),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (user_id, fruit_id) 
    );
    
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
"""

)

connection.commit()
connection.close()
print("Database created with starter fruits!")