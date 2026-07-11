from datetime import datetime
import sqlite3
from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta

# since we need a unique week we will use the trick of storing the monday 
def week_start_of(d: date) -> date:
    return d - timedelta(days=d.weekday())

app = Flask(__name__)
# dont allow anyone to change the cookie in production and pretend they are another user
app.secret_key = "dev-only-change-me" 

@app.template_filter("prettydate")
def prettydate(value):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%B %-d, %Y")
        except ValueError:
            continue
    return value

def get_db():
    db = sqlite3.connect("fruitloop.db")
    db.row_factory = sqlite3.Row
    return db

@app.route("/")
def home():
    db = get_db()
    
    fruits = db.execute("""
        SELECT f.id, f.name, f.emoji,
               ROUND(AVG(r.overall), 1)   AS avg_overall,
               ROUND(AVG(r.sweetness), 1) AS avg_sweetness,
               ROUND(AVG(r.juiciness), 1) AS avg_juiciness,
               COUNT(r.id) AS num_ratings
        FROM fruits f
        LEFT JOIN ratings r ON r.fruit_id = f.id
        GROUP BY f.id
        ORDER BY avg_overall DESC
    """).fetchall()
    
    db.close()
    return render_template("home.html", username=session.get("username"), fruits=fruits)

@app.route("/rate/<int:fruit_id>", methods=["GET", "POST"])
def rate(fruit_id):
    if "user_id" not in session:
        return redirect("/login")

    db = get_db()
    fruit = db.execute("SELECT * FROM fruits WHERE id = ?", (fruit_id,)).fetchone()
    if fruit is None:
        db.close()
        return "Fruit not found", 404
    locations = db.execute("SELECT * FROM locations ORDER BY nickname").fetchall()

    if request.method == "POST":
        location_id = request.form["location_id"]
        sweetness = int(request.form["sweetness"])
        juiciness = int(request.form["juiciness"])
        overall = int(request.form["overall"])
        purchase_date = request.form["purchase_date"]
        consumed_date = request.form["consumed_date"]

        consumed = date.fromisoformat(consumed_date)
        week_start = week_start_of(consumed)

        db.execute(
            """INSERT INTO ratings
               (user_id, fruit_id, location_id, sweetness, juiciness, overall,
                purchase_date, consumed_date, week_start)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (user_id, fruit_id, location_id, week_start)
               DO UPDATE SET sweetness = excluded.sweetness,
                             juiciness = excluded.juiciness,
                             overall = excluded.overall,
                             purchase_date = excluded.purchase_date,
                             consumed_date = excluded.consumed_date,
                             created_at = CURRENT_TIMESTAMP""",
            (session["user_id"], fruit_id, location_id,
             sweetness, juiciness, overall,
             purchase_date, consumed_date, week_start),
        )
        db.commit()
        db.close()
        session["last_location_id"] = int(location_id)
        return redirect(f"/fruit/{fruit_id}")

    db.close()
    today = date.today().isoformat()
    return render_template(
        "rate.html",
        fruit=fruit,
        locations=locations,
        today=today,
        last_location_id=session.get("last_location_id"),
    )


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

    averages = db.execute(
        """SELECT ROUND(AVG(overall), 1)   AS avg_overall,
                  ROUND(AVG(sweetness), 1) AS avg_sweetness,
                  ROUND(AVG(juiciness), 1) AS avg_juiciness,
                  COUNT(id) AS num_ratings
           FROM ratings WHERE fruit_id = ?""",
        (fruit_id,),
    ).fetchone()

    ratings = db.execute(
        """SELECT r.sweetness, r.juiciness, r.overall,
                  r.purchase_date, r.consumed_date,
                  l.nickname AS location
           FROM ratings r
           JOIN locations l ON l.id = r.location_id
           WHERE r.fruit_id = ?
           ORDER BY r.consumed_date DESC""",
        (fruit_id,),
    ).fetchall()
    db.close()
    return render_template("fruit.html", fruit=fruit, averages=averages, ratings=ratings)
    