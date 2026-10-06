"""Sign up, log in, log out, and who is logged in."""
import sqlite3
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, jsonify, redirect, request, session, url_for  
from werkzeug.security import check_password_hash, generate_password_hash
from yatra.db import get_db

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Login required"}), 401
        return f(*args, **kwargs)
    return wrapper
def page_login_required(view):                                          # ← NEW
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
    username = data.get("username","").strip()
    email    = data.get("email","").strip().lower()
    password = data.get("password","")
    if not username or not email or not password:
        return jsonify({"error":"username, email and password required"}), 400
    if len(password) < 6:
        return jsonify({"error":"Password must be at least 6 characters"}), 400
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, email, password) VALUES (?,?,?)",
                        (username, email, generate_password_hash(password))
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
    email = data.get("email","").strip().lower()
    pw    = data.get("password","")
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