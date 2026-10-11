"""HTML pages."""
from flask import Blueprint, redirect, render_template, request, session, url_for

from yatra.routes.auth import current_user_id, page_login_required

bp = Blueprint("pages", __name__)


@bp.route("/")
def home():
    return render_template("landing.html")


@bp.route("/explore")
def explore():
    return render_template("explore.html")


def safe_next(target, default="/"):
    """Only follow ?next= to a page on THIS site. Stops tricks like /login?next=https://evil.example."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return default


@bp.route("/login")
def login_page():
    if current_user_id():                       # already logged in: nothing to do here
        return redirect(safe_next(request.args.get("next")))
    return render_template("login.html")


@bp.route("/signup")
def signup_page():
    if current_user_id():
        return redirect(safe_next(request.args.get("next")))
    return render_template("signup.html")

@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("pages.home"))

@bp.route("/bag")
@page_login_required
def bag():
    return "My Bag - coming in Phase 8"