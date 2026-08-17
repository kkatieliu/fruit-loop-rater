import os
import sys
import subprocess
import tempfile

# Must run before "import app" anywhere in the test session, since app.py
# reads DATABASE_PATH/SECRET_KEY at import time. A fresh temp db keeps
# tests from ever touching the real fruitloop.db.
_tmpdir = tempfile.mkdtemp(prefix="fruitloop-test-")
_db_path = os.path.join(_tmpdir, "test.db")
os.environ["DATABASE_PATH"] = _db_path
os.environ["SECRET_KEY"] = "test-secret-key"

_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
subprocess.run(
    [sys.executable, os.path.join(_repo_root, "init_db.py")],
    check=True,
    env=os.environ,
    cwd=_repo_root,
)

sys.path.insert(0, _repo_root)

import pytest
import app as flask_app_module


@pytest.fixture()
def client():
    flask_app_module.app.config["TESTING"] = True
    with flask_app_module.app.test_client() as c:
        yield c


@pytest.fixture()
def db():
    import sqlite3
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


_counter = [0]


def unique_username(prefix="user"):
    _counter[0] += 1
    return f"{prefix}{_counter[0]}"


def register(client, username=None, password="testpass123"):
    username = username or unique_username()
    client.post(
        "/register",
        data={"username": username, "password": password, "email": f"{username}@example.com"},
    )
    return username
