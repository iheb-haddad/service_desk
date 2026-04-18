from __future__ import annotations

import os

from flask import Blueprint, abort, current_app, send_from_directory
from flask_login import current_user, login_required

from app.models import Attachment, UserRole

bp = Blueprint("attachments", __name__, url_prefix="/fichiers")


@bp.route("/<int:attachment_id>")
@login_required
def telecharger(attachment_id: int):
    att = Attachment.query.get_or_404(attachment_id)
    ticket = att.ticket

    allowed = False
    if current_user.role == UserRole.ADMIN:
        allowed = True
    elif ticket.demandeur_id == current_user.id:
        allowed = True
    elif ticket.assignee_id == current_user.id:
        allowed = True

    if not allowed:
        abort(403)

    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], "tickets", str(ticket.id))
    return send_from_directory(
        folder,
        att.nom_stocke,
        as_attachment=True,
        download_name=att.nom_fichier,
    )
