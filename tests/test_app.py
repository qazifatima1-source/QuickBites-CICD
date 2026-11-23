"""
Automated tests. Run with:  pytest
These are what your CI/CD pipeline will run on every code change.
Each test uses a fresh temporary database, so nothing real is touched.
"""
import pytest
import app as food_app


@pytest.fixture
def client(tmp_path):
    food_app.app.config["DATABASE_PATH"] = str(tmp_path / "test.db")
    food_app.app.config["TESTING"] = True
    food_app.init_db()
    return food_app.app.test_client()


def register_and_login(client, user="ali", pw="pass1234"):
    client.post("/register", data={"username": user, "password": pw})
    return client.post("/login", data={"username": user, "password": pw},
                       follow_redirects=True)


def test_health(client):
    assert client.get("/health").status_code == 200


def test_menu_requires_login(client):
    resp = client.get("/menu")
    assert resp.status_code == 302 and "/login" in resp.headers["Location"]


def test_register_login_and_see_menu(client):
    resp = register_and_login(client)
    assert b"Chicken Biryani" in resp.data


def test_wrong_password_rejected(client):
    client.post("/register", data={"username": "ali", "password": "pass1234"})
    resp = client.post("/login", data={"username": "ali", "password": "bad"})
    assert b"Wrong username or password" in resp.data


def test_place_order_and_see_it(client):
    register_and_login(client)
    resp = client.post("/menu", data={"qty_1": 2, "qty_5": 1}, follow_redirects=True)
    assert b"Order #1 placed" in resp.data
    assert b"Rs 1100" in resp.data  # 2 x 450 + 1 x 200


def test_empty_order_rejected(client):
    register_and_login(client)
    resp = client.post("/menu", data={}, follow_redirects=True)
    assert b"at least one item" in resp.data
