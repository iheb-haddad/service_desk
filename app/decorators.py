from __future__ import annotations

from functools import wraps
from typing import Iterable

from flask import flash, redirect, url_for
from flask_login import current_user

from app.models import UserRole


def role_required(*roles: UserRole | str):
    allowed = {r.value if isinstance(r, UserRole) else str(r) for r in roles}

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            if current_user.role.value not in allowed:
                flash("Accès refusé pour votre profil.", "error")
                return redirect(url_for("main.redirect_home"))
            return f(*args, **kwargs)

        return wrapped

    return decorator
