"""Escalade automatique lorsque le délai SLA est dépassé."""

from __future__ import annotations

from datetime import datetime

from app.extensions import db
from app.models import NotificationType, Ticket, TicketHistory, TicketStatus, TicketStatusCode
from app.services.notifications import creer_notification, notifier_admins
def process_escalations() -> int:
    """
    Passe en escalade les tickets ouverts dont la date d'échéance SLA est dépassée.
    Retourne le nombre de tickets traités.
    """
    now = datetime.utcnow()
    statut_escalade = TicketStatus.query.filter_by(code=TicketStatusCode.ESCALADE).first()
    statut_cree = TicketStatus.query.filter_by(code=TicketStatusCode.CREE).first()
    statut_encours = TicketStatus.query.filter_by(code=TicketStatusCode.EN_COURS).first()
    if not statut_escalade or not statut_cree or not statut_encours:
        return 0

    candidats = (
        Ticket.query.filter(
            Ticket.date_echeance_sla.isnot(None),
            Ticket.date_echeance_sla < now,
            Ticket.escalade_declenchee.is_(False),
            Ticket.statut_id.in_([statut_cree.id, statut_encours.id]),
        )
        .all()
    )

    count = 0
    for ticket in candidats:
        ticket.statut_id = statut_escalade.id
        ticket.escalade_declenchee = True
        ticket.date_mise_a_jour = now

        hist = TicketHistory(
            ticket_id=ticket.id,
            utilisateur_id=None,
            action="escalade_automatique",
            ancienne_valeur="dans_les_delais",
            nouvelle_valeur="depasse_sla",
        )
        db.session.add(hist)

        msg = (
            f"Le ticket « {ticket.titre} » (#{ticket.public_id[:8]}) a été escaladé : "
            f"dépassement du délai de traitement."
        )
        notifier_admins(msg, ticket_id=ticket.id, titre="Escalade SLA")

        if ticket.assignee_id:
            creer_notification(
                destinataire_id=ticket.assignee_id,
                type_notif=NotificationType.ESCALADE,
                message=msg,
                ticket_id=ticket.id,
                titre="Ticket escaladé",
            )

        creer_notification(
            destinataire_id=ticket.demandeur_id,
            type_notif=NotificationType.ESCALADE,
            message=(
                f"Votre demande « {ticket.titre} » a été escaladée pour traitement prioritaire."
            ),
            ticket_id=ticket.id,
            titre="Mise à jour de votre ticket",
        )

        count += 1

    if count:
        db.session.commit()
    return count
