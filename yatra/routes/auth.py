"""Sign up, log in, log out, and who is logged in."""
import re
import sqlite3
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, jsonify, redirect, request, session, url_for  
from werkzeug.security import check_password_hash, generate_password_hash
from yatra.db import get_db

bp = Blueprint("auth", __name__, url_prefix="/api/auth")
EMAIL_RE    = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
MIN_PASSWORD = 8


def validate_registration(username, email, password):
    """Return a dict of {field: problem}. Empty dict means everything is fine."""
    errors = {}
    if not USERNAME_RE.match(username):
        errors["username"] = "Username must be 3-20 characters: letters, numbers or underscores."
    if not EMAIL_RE.match(email):
        errors["email"] = "Enter a valid email address, like name@example.com."
    if len(password) < MIN_PASSWORD:
        errors["password"] = f"Password must be at least {MIN_PASSWORD} characters."
    return errors

def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Login required"}), 401
        return f(*args, **kwargs)
    return wrapper

def page_login_required(view):                                          
    """For HTML pages: send logged-out visitors to the login page, then back here."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            here = request.full_path if request.query_string else request.path
            return redirect(url_for("pages.login_page", next=here))
        return view(*args, **kwargs)
    return wrapper  

def current_user_id():
    return session.get("user_id")


@bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username") or "").strip()
    email    = str(data.get("email") or "").strip().lower()
    password = str(data.get("password") or "")

    errors = validate_registration(username, email, password)
    if errors:
        first = next(iter(errors.values()))
        return jsonify({"error": first, "errors": errors}), 400
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, email, password, created_at) VALUES (?,?,?,?)",
            (username, email, generate_password_hash(password), now_iso())
        )
        conn.commit()
        row = conn.execute("SELECT id,username,email FROM users WHERE email=?", (email,)).fetchone()
        session["user_id"]  = row["id"]
        session["username"] = row["username"]
        return jsonify({"message":"Registered successfully","user":{"id":row["id"],"username":row["username"],"email":row["email"]}})
    except sqlite3.IntegrityError as e:
        msg = "Username already taken" if "username" in str(e) else "Email already registered"
        return jsonify({"error": msg}), 409
    finally:
        conn.close()


@bp.route("/login", methods=["POST"])
def login():
    data  = request.get_json(silent=True) or {}
    email = str(data.get("email") or "").strip().lower()
    pw    = str(data.get("password") or "")
    if not email or not pw:
        return jsonify({"error":"Email and password are required"}), 400
    conn  = get_db()
    row   = conn.execute(
        "SELECT * FROM users WHERE email=?", (email,)
    ).fetchone()
    if not row or not check_password_hash(row["password"], pw):
        conn.close()
        return jsonify({"error":"Invalid email or password"}), 401
    conn.execute("UPDATE users SET last_login=? WHERE id=?", (now_iso(), row["id"]))
    conn.commit(); conn.close()
    session["user_id"]  = row["id"]
    session["username"] = row["username"]
    return jsonify({"message":"Logged in","user":{"id":row["id"],"username":row["username"],"email":row["email"]}})


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message":"Logged out"})


@bp.route("/me")
def me():
    uid = current_user_id()
    if not uid: return jsonify({"user":None})
    conn = get_db()
    row  = conn.execute("SELECT id,username,email,created_at,last_login FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    if not row: return jsonify({"user":None})
    return jsonify({"user":dict(row)})