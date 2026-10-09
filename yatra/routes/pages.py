"""HTML pages."""
from flask import Blueprint, render_template

from yatra.routes.auth import page_login_required

bp = Blueprint("pages", __name__)


@bp.route("/")
def home():
    return render_template("landing.html")


@bp.route("/explore")
def explore():
    return render_template("explore.html")


@bp.route("/login")
def login_page():
    return "Login page - coming in Phase 8"

@bp.route("/signup")
def signup_page():
    return "Sign up page - coming in Phase 8"


@bp.route("/bag")
@page_login_required
def bag():
    return "My Bag - coming in Phase 8"