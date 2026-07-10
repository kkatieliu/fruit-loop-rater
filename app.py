import sqlite3
from flask import Flask, render_template, request, redirect

app = Flask(__name__)

def get_db():
    db = sqlite3.connect("fruitloop.db")
    db.row_factory = sqlite3.Row
    return db

@app.route("/")
def home():
    db = get_db()
    fruits = db.execute("SELECT * FROM fruits ORDER BY name").fetchall()
    db.close()
    return render_template("home.html", name="Katie", fruits=fruits)

@app.route("/rate", methods=["POST"])
def rate():
    fruit_id = request.form["fruit_id"]
    score = request.form["score"]
    db = get_db()
    db.execute("INSERT INTO ratings (fruit_id, score) VALUES (?, ?)", (fruit_id, score))
    db.commit()
    db.close()
    return redirect("/")