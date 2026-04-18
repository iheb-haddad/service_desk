from __future__ import annotations

from app.extensions import db
from app.models import Notification, NotificationType, User, UserRole


def creer_notification(
    *,
    destinataire_id: int,
    type_notif: NotificationType,
    message: str,
    ticket_id: int | None = None,
    titre: str | None = None,
) -> Notification:
    n = Notification(
        destinataire_id=destinataire_id,
        ticket_id=ticket_id,
        type_notif=type_notif,
        titre=titre,
        message=message,
        lue=False,
    )
    db.session.add(n)
    return n


def notifier_admins(message: str, *, ticket_id: int | None = None, titre: str | None = None) -> None:
    admins = User.query.filter_by(role=UserRole.ADMIN, actif=True).all()
    for a in admins:
        creer_notification(
            destinataire_id=a.id,
            type_notif=NotificationType.ESCALADE,
            message=message,
            ticket_id=ticket_id,
            titre=titre or "Alerte administrateur",
        )
