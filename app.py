"""
Simple Food Ordering App  (Monolith: Flask + SQLite)
====================================================
One file = whole backend. Pages are rendered by Flask templates (templates/).

Pages / routes
  /            -> redirects to menu or login
  /register    -> create account
  /login       -> sign in
  /logout      -> sign out
  /menu        -> view menu, choose quantities, place order
  /orders      -> list of my past orders
  /health      -> health check (used later by CI/CD, load balancer, Docker)

Settings come from ENVIRONMENT VARIABLES so the same code runs on
your laptop, in Docker, or on AWS without changing code:
  SECRET_KEY     -> session signing key (set a real one in production!)
  DATABASE_PATH  -> where the SQLite file lives (default: food_app.db)
"""
import os
import sqlite3
from functools import wraps

from flask import (Flask, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

# --------------------------------------------------------------------------
# 1. APP SETUP
# --------------------------------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config["DATABASE_PATH"] = os.environ.get("DATABASE_PATH", "food_app.db")

# Starting menu. Edit this list to change the default menu (name, price, description).
# It is only inserted when the menu table is empty.
DEFAULT_MENU = [
    ("Chicken Biryani", 450, "Fragrant rice with spiced chicken"),
    ("Beef Burger", 550, "Grilled patty, cheese, lettuce, fries"),
    ("Chicken Karahi", 900, "Tomato and ginger karahi, serves 2"),
    ("Paratha Roll", 300, "Chicken tikka in a flaky paratha"),
    ("Mango Lassi", 200, "Chilled yogurt and mango drink"),
]


# --------------------------------------------------------------------------
# 2. DATABASE HELPERS  (plain sqlite3, no extra libraries)
# --------------------------------------------------------------------------
def get_db():
    """Open one DB connection per request and reuse it."""
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE_PATH"])
        g.db.row_factory = sqlite3.Row  # lets us use row["name"]
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    """Close the DB connection at the end of each request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create tables if they don't exist and add the default menu."""
    db = sqlite3.connect(app.config["DATABASE_PATH"])
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS menu_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            price       INTEGER NOT NULL,
            description TEXT
        );
        CREATE TABLE IF NOT EXISTS orders (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL REFERENCES users(id),
            total      INTEGER NOT NULL,
            status     TEXT NOT NULL DEFAULT 'Placed',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id     INTEGER NOT NULL REFERENCES orders(id),
            menu_item_id INTEGER NOT NULL REFERENCES menu_items(id),
            quantity     INTEGER NOT NULL,
            unit_price   INTEGER NOT NULL
        );
        """
    )
    if db.execute("SELECT COUNT(*) FROM menu_items").fetchone()[0] == 0:
        db.executemany(
            "INSERT INTO menu_items (name, price, description) VALUES (?, ?, ?)",
            DEFAULT_MENU,
        )
    db.commit()
    db.close()


# --------------------------------------------------------------------------
# 3. LOGIN HELPER  (decorator: protects pages that need a logged-in user)
# --------------------------------------------------------------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


# --------------------------------------------------------------------------
# 4. ROUTES
# --------------------------------------------------------------------------
@app.route("/")
def home():
    return redirect(url_for("menu" if "user_id" in session else "login"))


@app.route("/health")
def health():
    """Return 200 OK if the app is alive. CI/CD and AWS health checks use this."""
    return {"status": "ok"}, 200


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or len(password) < 4:
            flash("Enter a username and a password of at least 4 characters.")
        else:
            try:
                get_db().execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash(password)),  # never store plain passwords
                )
                get_db().commit()
                flash("Account created. You can log in now.")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("That username is already taken.")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("menu"))
        flash("Wrong username or password.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/menu", methods=["GET", "POST"])
@login_required
def menu():
    db = get_db()
    items = db.execute("SELECT * FROM menu_items ORDER BY id").fetchall()

    if request.method == "POST":
        # Each menu item has a form field named "qty_<id>"
        lines, total = [], 0
        for item in items:
            try:
                qty = int(request.form.get(f"qty_{item['id']}", 0))
            except ValueError:
                qty = 0
            if qty > 0:
                lines.append((item["id"], qty, item["price"]))
                total += qty * item["price"]

        if not lines:
            flash("Choose at least one item before placing an order.")
        else:
            cur = db.execute(
                "INSERT INTO orders (user_id, total) VALUES (?, ?)",
                (session["user_id"], total),
            )
            order_id = cur.lastrowid
            db.executemany(
                "INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price) "
                "VALUES (?, ?, ?, ?)",
                [(order_id, i, q, p) for i, q, p in lines],
            )
            db.commit()
            flash(f"Order #{order_id} placed. Total: Rs {total}.")
            return redirect(url_for("orders"))

    return render_template("menu.html", items=items)


@app.route("/orders")
@login_required
def orders():
    db = get_db()
    my_orders = db.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC",
        (session["user_id"],),
    ).fetchall()
    # Attach the items of each order so the template can list them
    result = []
    for o in my_orders:
        lines = db.execute(
            "SELECT m.name, oi.quantity, oi.unit_price FROM order_items oi "
            "JOIN menu_items m ON m.id = oi.menu_item_id WHERE oi.order_id = ?",
            (o["id"],),
        ).fetchall()
        result.append({"order": o, "lines": lines})
    return render_template("orders.html", orders=result)


# --------------------------------------------------------------------------
# 5. START-UP
# --------------------------------------------------------------------------
init_db()  # runs when the app starts (also under gunicorn)

if __name__ == "__main__":
    # Local development only. In production use gunicorn (see Dockerfile).
    app.run(host="0.0.0.0", port=5000, debug=False)
