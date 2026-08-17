from datetime import date, timedelta

from conftest import register, unique_username


def fruit_id(db, name="Watermelon"):
    return db.execute("SELECT id FROM fruits WHERE name = ?", (name,)).fetchone()["id"]


def location_id(db, nickname="Brighton"):
    return db.execute("SELECT id FROM locations WHERE nickname = ?", (nickname,)).fetchone()["id"]


def rate(client, fid, overall, sweetness=5, juiciness=5, firmness=5,
         loc=1, purchase_date=None, consumed_date=None):
    today = date.today().isoformat()
    return client.post(
        f"/rate/{fid}",
        data={
            "location_id": loc,
            "overall": overall,
            "sweetness": sweetness,
            "juiciness": juiciness,
            "firmness": firmness,
            "purchase_date": purchase_date or today,
            "consumed_date": consumed_date or today,
        },
    )


# ---- auth ----

def test_register_creates_user_and_logs_in(client):
    username = unique_username()
    resp = client.post(
        "/register",
        data={"username": username, "password": "testpass123", "email": f"{username}@example.com"},
    )
    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert sess["username"] == username


def test_register_duplicate_username_rejected(client):
    username = register(client)
    client.get("/logout")
    resp = client.post(
        "/register",
        data={"username": username, "password": "different", "email": "x@example.com"},
    )
    assert resp.status_code == 200
    assert b"taken" in resp.data.lower()


def test_login_wrong_password_rejected(client):
    username = register(client, password="correcthorse")
    client.get("/logout")
    resp = client.post("/login", data={"username": username, "password": "wrong"})
    assert resp.status_code == 200
    assert b"invalid" in resp.data.lower()


def test_login_correct_password_succeeds(client):
    username = register(client, password="correcthorse")
    client.get("/logout")
    resp = client.post("/login", data={"username": username, "password": "correcthorse"})
    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert sess["username"] == username


def test_logout_clears_session(client):
    register(client)
    client.get("/logout")
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_rate_requires_login(client):
    resp = client.get("/rate/1")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# ---- fruit pages ----

def test_home_page_lists_seeded_fruits(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Watermelon" in resp.data
    assert b"Strawberry" in resp.data


def test_fruit_detail_404_for_bad_id(client):
    resp = client.get("/fruit/999999")
    assert resp.status_code == 404


def test_rate_404_for_bad_fruit_id(client, db):
    register(client)
    resp = client.get("/rate/999999")
    assert resp.status_code == 404


# ---- rating submission: multiple ratings allowed, not upserted ----

def test_multiple_ratings_same_fruit_location_week_both_kept(client, db):
    register(client)
    fid = fruit_id(db, "Banana")
    rate(client, fid, overall=2)
    rate(client, fid, overall=10)
    rows = db.execute(
        "SELECT overall FROM ratings WHERE fruit_id = ?", (fid,)
    ).fetchall()
    assert len(rows) == 2, "resubmitting should add a new row, not overwrite the old one"


def test_consumed_before_purchased_rejected(client, db):
    register(client)
    fid = fruit_id(db, "Tomato")
    today = date.today()
    resp = rate(
        client, fid, overall=5,
        purchase_date=today.isoformat(),
        consumed_date=(today - timedelta(days=1)).isoformat(),
    )
    assert resp.status_code == 200
    assert b"on or after" in resp.data.lower()
    rows = db.execute("SELECT * FROM ratings WHERE fruit_id = ?", (fid,)).fetchall()
    assert len(rows) == 0


# ---- averaging model: one vote per user, not per raw rating ----

def test_home_page_averages_per_user_not_per_row(client, db):
    fid = fruit_id(db, "Ogrange")
    loc = location_id(db, "Brighton")

    register(client, username=unique_username("avgA"))
    rate(client, fid, overall=2, loc=loc)
    rate(client, fid, overall=10, loc=loc)  # same user, same slot -> averages to 6
    client.get("/logout")

    register(client, username=unique_username("avgB"))
    rate(client, fid, overall=8, loc=loc)  # different user -> separate vote
    client.get("/logout")

    resp = client.get("/")
    html = resp.data.decode()
    # fruit-level avg should be (6 + 8) / 2 = 7, not (2+10+8)/3 = 6.67 -> 7 either way here,
    # so assert against the fruit detail page's num_ratings instead, which is unambiguous:
    # 2 raw submissions from user A collapse into 1 slot, + 1 from user B = 2 "ratings".
    detail = client.get(f"/fruit/{fid}").data.decode()
    assert 'class="meter-value">7/10' in detail
    assert "2 rating" in detail  # slot count, not raw row count (which is 3)


def test_tier_count_uses_distinct_slots_not_raw_submissions(client, db):
    username = unique_username("tierspam")
    register(client, username=username)
    fid = fruit_id(db, "Kiwi")
    # Rate the same fruit/location/week 5 times - should count as 1 slot for tier purposes.
    for overall in [1, 2, 3, 4, 5]:
        rate(client, fid, overall=overall)
    profile = client.get("/profile").data.decode()
    assert "1 rating" in profile
    assert "5 rating" not in profile


# ---- rolling 7-day window vs all-time ----

def test_rating_outside_7_day_window_excluded_from_recent_but_counted_alltime(client, db):
    register(client)
    fid = fruit_id(db, "Pear")
    old_date = (date.today() - timedelta(days=10)).isoformat()
    rate(client, fid, overall=4, purchase_date=old_date, consumed_date=old_date)

    detail = client.get(f"/fruit/{fid}").data.decode()
    assert "No ratings in the last 7 days" in detail
    assert "All-time" in detail
    assert "⭐ 4" in detail  # all-time average still reflects the old rating


def test_rating_within_7_day_window_included(client, db):
    register(client)
    fid = fruit_id(db, "Pineapple")
    recent_date = (date.today() - timedelta(days=6)).isoformat()
    rate(client, fid, overall=9, purchase_date=recent_date, consumed_date=recent_date)

    detail = client.get(f"/fruit/{fid}").data.decode()
    assert 'class="meter-value">9/10' in detail


# ---- delete ownership ----

def test_cannot_delete_other_users_rating(client, db):
    fid = fruit_id(db, "Strawberry")
    register(client, username=unique_username("ownerA"))
    rate(client, fid, overall=6)
    rating_row = db.execute(
        "SELECT id FROM ratings WHERE fruit_id = ? ORDER BY id DESC LIMIT 1", (fid,)
    ).fetchone()
    rating_id = rating_row["id"]
    client.get("/logout")

    register(client, username=unique_username("attackerB"))
    client.post(f"/delete-rating/{rating_id}")

    still_there = db.execute("SELECT id FROM ratings WHERE id = ?", (rating_id,)).fetchone()
    assert still_there is not None, "a user must not be able to delete another user's rating"


# ---- shared header / 404 handler ----

def test_404_uses_styled_error_page(client):
    resp = client.get("/fruit/999999")
    assert resp.status_code == 404
    assert b"Nothing here" in resp.data


def test_header_shows_login_link_when_logged_out(client):
    resp = client.get("/")
    assert b'class="nav-cta"' in resp.data
    assert b"Log in" in resp.data


def test_header_shows_username_and_tier_when_logged_in(client):
    username = register(client)
    resp = client.get("/")
    assert username.encode() in resp.data
    assert b"nav-tier-emoji" in resp.data
    assert b"Log out" in resp.data


def test_can_delete_own_rating(client, db):
    fid = fruit_id(db, "Watermelon")
    register(client)
    rate(client, fid, overall=6)
    rating_row = db.execute(
        "SELECT id FROM ratings WHERE fruit_id = ? ORDER BY id DESC LIMIT 1", (fid,)
    ).fetchone()
    rating_id = rating_row["id"]

    client.post(f"/delete-rating/{rating_id}")
    gone = db.execute("SELECT id FROM ratings WHERE id = ?", (rating_id,)).fetchone()
    assert gone is None
