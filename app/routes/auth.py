from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user

from app.extensions import db
from app.models import User

bp = Blueprint("auth", __name__, url_prefix="")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.redirect_home"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not email or not password:
            flash("Veuillez renseigner l'adresse e-mail et le mot de passe.", "error")
            return render_template("auth/login.html")

        user = User.query.filter_by(email=email, actif=True).first()
        if user and user.check_password(password):
            user.derniere_connexion = datetime.utcnow()
            db.session.commit()
            login_user(user, remember=True)
            flash("Connexion réussie.", "success")
            return redirect(url_for("main.redirect_home"))

        flash("Identifiants incorrects ou compte désactivé.", "error")

    return render_template("auth/login.html")


@bp.route("/logout")
def logout():
    logout_user()
    flash("Vous êtes déconnecté.", "info")
    return redirect(url_for("auth.login"))
