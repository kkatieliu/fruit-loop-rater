import sqlite3
from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
import os   # add to the imports at the top
from dotenv import load_dotenv
load_dotenv()   # reads .env into os.environ, if the file exists

DB_PATH = os.environ.get("DATABASE_PATH", "fruitloop.db")


# since we need a unique week we will use the trick of storing the monday 
def week_start_of(d: date) -> date:
    return d - timedelta(days=d.weekday())

TIERS = [
    (75, "👑", "Tier 5 Rater"),
    (35, "🌹", "Tier 4 Rater"),
    (15, "🌸", "Tier 3 Rater"),
    (5,  "🌿", "Tier 2 Rater"),
    (0,  "🌱", "Tier 1 Rater"),
]

def tier_for(count):
    for threshold, emoji, name in TIERS:
        if count >= threshold:
            return {"emoji": emoji, "name": name}

app = Flask(__name__)
# dont allow anyone to change the cookie in production and pretend they are another user
app.secret_key = os.environ["SECRET_KEY"]   # square brackets: no key, no app — KeyError at startup

@app.template_filter("prettydate")
def prettydate(value):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%B %-d, %Y")
        except ValueError:
            continue
    return value

def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db

@app.route("/")
def home():
    db = get_db()
    
    this_week = week_start_of(date.today())

    fruits = db.execute("""
        SELECT f.id, f.name, f.emoji,
               CAST(ROUND(AVG(r.firmness), 0) AS INTEGER)   AS avg_firmness,
               CAST(ROUND(AVG(r.sweetness), 0) AS INTEGER) AS avg_sweetness,
               CAST(ROUND(AVG(r.juiciness), 0) AS INTEGER) AS avg_juiciness,
               COUNT(r.id) AS num_ratings
        FROM fruits f
        LEFT JOIN ratings r ON r.fruit_id = f.id AND r.week_start = ?
        GROUP BY f.id
        ORDER BY num_ratings DESC, f.name
    """, (this_week,)).fetchall()
    
    
    
    my_tier = None
    if "user_id" in session:
        count = db.execute(
            "SELECT COUNT(*) AS c FROM ratings WHERE user_id = ?",
            (session["user_id"],),
        ).fetchone()["c"]
        my_tier = tier_for(count)
        
    db.close()
    return render_template("home.html", username=session.get("username"), fruits=fruits, my_tier=my_tier)

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
        firmness = int(request.form["firmness"])
        purchase_date = request.form["purchase_date"]
        consumed_date = request.form["consumed_date"]

        purchased = date.fromisoformat(purchase_date)
        consumed = date.fromisoformat(consumed_date)

        if consumed < purchased:
            db.close()
            return render_template(
                "rate.html",
                fruit=fruit,
                locations=locations,
                today=date.today().isoformat(),
                last_location_id=session.get("last_location_id"),
                error="Consumed date must be on or after the purchase date.",
            )

        week_start = week_start_of(consumed)

        db.execute(
            """INSERT INTO ratings
               (user_id, fruit_id, location_id, sweetness, juiciness, firmness,
                purchase_date, consumed_date, week_start)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (user_id, fruit_id, location_id, week_start)
               DO UPDATE SET sweetness = excluded.sweetness,
                             juiciness = excluded.juiciness,
                             firmness = excluded.firmness,
                             purchase_date = excluded.purchase_date,
                             consumed_date = excluded.consumed_date,
                             created_at = CURRENT_TIMESTAMP""",
            (session["user_id"], fruit_id, location_id,
             sweetness, juiciness, firmness,
             purchase_date, consumed_date, week_start),
        )
        db.commit()
        db.close()
        session["last_location_id"] = int(location_id)
        return redirect(f"/fruit/{fruit_id}")
    
    already = db.execute(
        """SELECT l.nickname FROM ratings r
           JOIN locations l ON l.id = r.location_id
           WHERE r.user_id = ? AND r.fruit_id = ? AND r.week_start = ?""",
        (session["user_id"], fruit_id, week_start_of(date.today())),
    ).fetchall()
    already_at = [row["nickname"] for row in already]

    db.close()
    today = date.today().isoformat()
    
    return render_template(
        "rate.html",
        fruit=fruit,
        locations=locations,
        today=today,
        last_location_id=session.get("last_location_id"),
        already_at=already_at,
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
    location_id = request.args.get("location", type=int)         

    db = get_db()
    fruit = db.execute("SELECT * FROM fruits WHERE id = ?", (fruit_id,)).fetchone()
    if fruit is None:
        db.close()
        return "Fruit not found", 404

    locations = db.execute("SELECT * FROM locations ORDER BY nickname").fetchall()  

    loc_filter = "AND location_id = ?" if location_id else ""    
    loc_params = (location_id,) if location_id else ()           
    
    this_week = week_start_of(date.today())

    this_week_avg = db.execute(
        f"""SELECT CAST(ROUND(AVG(firmness), 0) AS INTEGER)   AS avg_firmness,
                   CAST(ROUND(AVG(sweetness), 0) AS INTEGER) AS avg_sweetness,
                   CAST(ROUND(AVG(juiciness), 0) AS INTEGER) AS avg_juiciness,
                   COUNT(id) AS num_ratings
            FROM ratings
            WHERE fruit_id = ? AND week_start = ? {loc_filter}""",
        (fruit_id, this_week, *loc_params),
    ).fetchone()

    averages = db.execute(
        f"""SELECT CAST(ROUND(AVG(firmness), 0) AS INTEGER)   AS avg_firmness,
                   CAST(ROUND(AVG(sweetness), 0) AS INTEGER) AS avg_sweetness,
                   CAST(ROUND(AVG(juiciness), 0) AS INTEGER) AS avg_juiciness,
                   COUNT(id) AS num_ratings
            FROM ratings WHERE fruit_id = ? {loc_filter}""",
        (fruit_id, *loc_params),
    ).fetchone()

    ratings = db.execute(
        f"""SELECT r.sweetness, r.juiciness, r.firmness,
                   r.purchase_date, r.consumed_date,
                   l.nickname AS location,
                   (SELECT COUNT(*) FROM ratings r2
                    WHERE r2.user_id = r.user_id) AS rater_count
            FROM ratings r
            JOIN locations l ON l.id = r.location_id
            WHERE r.fruit_id = ? {loc_filter}
            ORDER BY r.consumed_date DESC""",
        (fruit_id, *loc_params),
    ).fetchall()

    weekly = db.execute(
        f"""SELECT week_start,
                   CAST(ROUND(AVG(firmness), 0) AS INTEGER)   AS avg_firmness,
                   CAST(ROUND(AVG(sweetness), 0) AS INTEGER) AS avg_sweetness,
                   CAST(ROUND(AVG(juiciness), 0) AS INTEGER) AS avg_juiciness,
                   COUNT(id) AS num_ratings
            FROM ratings
            WHERE fruit_id = ? {loc_filter}
            GROUP BY week_start
            ORDER BY week_start DESC""",
        (fruit_id, *loc_params),
    ).fetchall()

    my_weekly = {}
    if "user_id" in session:
        rows = db.execute(
            f"""SELECT week_start, sweetness, juiciness, firmness
                FROM ratings
                WHERE fruit_id = ? AND user_id = ? {loc_filter}""",
            (fruit_id, session["user_id"], *loc_params),
        ).fetchall()
        my_weekly = {r["week_start"]: r for r in rows}

    db.close()
    return render_template("fruit.html", fruit=fruit, averages=averages,
                           ratings=ratings, weekly=weekly, my_weekly=my_weekly, this_week_avg=this_week_avg,
                           locations=locations, selected_location=location_id,
                           tier_for=tier_for)
    
@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect("/login")

    db = get_db()

    my_ratings = db.execute(
        """SELECT r.sweetness, r.juiciness, r.firmness,
                r.purchase_date, r.consumed_date, r.week_start,
                f.name AS fruit_name, f.emoji AS fruit_emoji, f.id AS fruit_id,
                l.nickname AS location
        FROM ratings r
        JOIN fruits f ON f.id = r.fruit_id
        JOIN locations l ON l.id = r.location_id
        WHERE r.user_id = ?
        ORDER BY r.consumed_date DESC""",
        (session["user_id"],),
    ).fetchall()
    
    by_location = {}
    for r in my_ratings:
        loc = r["location"]
        week = r["week_start"]
        by_location.setdefault(loc, {}).setdefault(week, []).append(r)

    count = len(my_ratings)
    my_tier = tier_for(count)

    next_tier_at = None
    for threshold, _, _ in TIERS:
        if count < threshold:
            next_tier_at = threshold   # keep looking: we want the smallest one above count

    db.close()
    return render_template("profile.html", ratings=my_ratings,
                        count=count, my_tier=my_tier,
                        next_tier_at=next_tier_at, by_location=by_location)