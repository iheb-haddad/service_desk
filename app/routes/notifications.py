from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Notification, UserRole

bp = Blueprint("notifications", __name__, url_prefix="/notifications")


def _lien_pour_notification(n: Notification) -> str:
    """URL relative pour ouvrir le ticket lié ou la liste des notifications."""
    if not n.ticket_id or not n.ticket:
        return url_for("notifications.liste")
    pid = n.ticket.public_id
    role = current_user.role
    if role == UserRole.ADMIN:
        return url_for("admin.detail_ticket", public_id=pid)
    if role == UserRole.AGENT_IT:
        return url_for("agent.detail_ticket", public_id=pid)
    return url_for("employe.detail_ticket", public_id=pid)


@bp.route("/")
@login_required
def liste():
    items = (
        Notification.query.filter_by(destinataire_id=current_user.id)
        .order_by(Notification.date_creation.desc())
        .limit(80)
        .all()
    )
    return render_template("notifications/list.html", items=items)


@bp.route("/<int:nid>/lue", methods=["POST"])
@login_required
def marquer_lue(nid: int):
    n = Notification.query.get_or_404(nid)
    if n.destinataire_id != current_user.id:
        return redirect(url_for("notifications.liste"))
    n.lue = True
    db.session.commit()
    if n.ticket_id and n.ticket:
        role = current_user.role
        if role == UserRole.ADMIN:
            return redirect(url_for("admin.detail_ticket", public_id=n.ticket.public_id))
        if role == UserRole.AGENT_IT:
            return redirect(url_for("agent.detail_ticket", public_id=n.ticket.public_id))
        return redirect(url_for("employe.detail_ticket", public_id=n.ticket.public_id))
    return redirect(url_for("notifications.liste"))


@bp.route("/api/non-lues")
@login_required
def count_non_lues():
    c = Notification.query.filter_by(destinataire_id=current_user.id, lue=False).count()
    return jsonify({"count": c})


@bp.route("/api/nouvelles")
@login_required
def api_nouvelles():
    """
    Notifications créées après l'id `apres` (polling pour toasts temps quasi réel).
    """
    apres = request.args.get("apres", type=int, default=0)
    rows = (
        Notification.query.options(joinedload(Notification.ticket))
        .filter(
            Notification.destinataire_id == current_user.id,
            Notification.id > apres,
        )
        .order_by(Notification.id.asc())
        .limit(30)
        .all()
    )
    items = []
    for n in rows:
        msg = n.message or ""
        if len(msg) > 220:
            msg = msg[:217] + "…"
        items.append(
            {
                "id": n.id,
                "titre": n.titre or "Notification",
                "message": msg,
                "lien": _lien_pour_notification(n),
            }
        )
    return jsonify({"items": items})
