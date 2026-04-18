from __future__ import annotations

from app.extensions import db
from app.models import TicketHistory


def log_action(
    ticket_id: int,
    utilisateur_id: int | None,
    action: str,
    ancienne: str | None = None,
    nouvelle: str | None = None,
) -> None:
    h = TicketHistory(
        ticket_id=ticket_id,
        utilisateur_id=utilisateur_id,
        action=action,
        ancienne_valeur=ancienne,
        nouvelle_valeur=nouvelle,
    )
    db.session.add(h)
