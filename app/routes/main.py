from flask import Blueprint, redirect, url_for
from flask_login import current_user

from app.models import UserRole

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.redirect_home"))
    return redirect(url_for("auth.login"))


@bp.route("/home")
def redirect_home():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    role = current_user.role
    if role == UserRole.ADMIN:
        return redirect(url_for("admin.dashboard"))
    if role == UserRole.AGENT_IT:
        return redirect(url_for("agent.dashboard"))
    return redirect(url_for("employe.dashboard"))
