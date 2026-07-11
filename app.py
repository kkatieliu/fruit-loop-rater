from datetime import datetime
import sqlite3
from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime   # add to the imports at the top of the file

app = Flask(__name__)
# dont allow anyone to change the cookie in production and pretend they are another user
app.secret_key = "dev-only-change-me" 


@app.template_filter("prettydate")
def prettydate(value):
    dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    return dt.strftime("%B %-d, %Y")


def get_db():
    db = sqlite3.connect("fruitloop.db")
    db.row_factory = sqlite3.Row
    return db

@app.route("/")
def home():
    db = get_db()
    fruits = db.execute("""
        SELECT f.id, f.name, f.emoji,
               ROUND(AVG(r.score), 1) AS avg_score,
               COUNT(r.id) AS num_ratings
        FROM fruits f
        LEFT JOIN ratings r ON r.fruit_id = f.id
        GROUP BY f.id
        ORDER BY avg_score DESC
    """).fetchall()
    db.close()
    return render_template("home.html", username=session.get("username"), fruits=fruits)

@app.route("/rate", methods=["POST"])
def rate():
    if "user_id" not in session:
        return redirect("/login")

    fruit_id = request.form["fruit_id"]
    score = request.form["score"]

    db = get_db()
    db.execute(
        """INSERT INTO ratings (user_id, fruit_id, score)
           VALUES (?, ?, ?)
           ON CONFLICT (user_id, fruit_id)
           DO UPDATE SET score = excluded.score, created_at = CURRENT_TIMESTAMP""",
        (session["user_id"], fruit_id, score),
    )
    db.commit()
    db.close()
    return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if not username or not password:
            return render_template("register.html", error="Both fields are required.")

        db = get_db()
        existing = db.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            db.close()
            return render_template("register.html", error="That username is taken.")

        cursor = db.execute(                                   
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, generate_password_hash(password)),
        )
        db.commit()
        new_user_id = cursor.lastrowid                        
        db.close()

        session["user_id"] = new_user_id                      
        session["username"] = username                         
        return redirect("/")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        db.close()

        if user is None or not check_password_hash(user["password_hash"], password):
            return render_template("login.html", error="Invalid username or password.")

        session["user_id"] = user["id"]
        session["username"] = user["username"]
        return redirect("/")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/fruit/<int:fruit_id>")
def fruit_detail(fruit_id):
    db = get_db()
    fruit = db.execute(
        "SELECT * FROM fruits WHERE id = ?", (fruit_id,)
    ).fetchone()

    if fruit is None:
        db.close()
        return "Fruit not found", 404

    ratings = db.execute(
        """SELECT score, created_at
           FROM ratings
           WHERE fruit_id = ?
           ORDER BY created_at DESC""",
        (fruit_id,),
    ).fetchall()
    db.close()
    return render_template("fruit.html", fruit=fruit, ratings=ratings)