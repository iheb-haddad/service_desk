from __future__ import annotations

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.decorators import role_required
from app.extensions import db
from app.models import (
    Comment,
    NotificationType,
    Ticket,
    TicketHistory,
    TicketStatus,
    TicketStatusCode,
    UserRole,
)
from app.services.history import log_action
from app.services.notifications import creer_notification

bp = Blueprint("agent", __name__, url_prefix="/agent")


@bp.route("/")
@role_required(UserRole.AGENT_IT)
def dashboard():
    tickets = (
        Ticket.query.filter_by(assignee_id=current_user.id)
        .order_by(Ticket.date_creation.desc())
        .limit(100)
        .all()
    )
    return render_template("agent/dashboard.html", tickets=tickets)


@bp.route("/tickets/<public_id>")
@role_required(UserRole.AGENT_IT)
def detail_ticket(public_id: str):
    ticket = Ticket.query.filter_by(public_id=public_id).first_or_404()
    if ticket.assignee_id != current_user.id:
        flash("Ce ticket ne vous est pas assigné.", "error")
        return redirect(url_for("agent.dashboard"))

    historique = (
        TicketHistory.query.filter_by(ticket_id=ticket.id)
        .order_by(TicketHistory.date_action.asc())
        .all()
    )
    statuts = TicketStatus.query.order_by(TicketStatus.id).all()
    return render_template(
        "agent/ticket_detail.html",
        ticket=ticket,
        historique=historique,
        statuts=statuts,
    )


@bp.route("/tickets/<public_id>/commentaire", methods=["POST"])
@role_required(UserRole.AGENT_IT)
def ajouter_commentaire(public_id: str):
    ticket = Ticket.query.filter_by(public_id=public_id).first_or_404()
    if ticket.assignee_id != current_user.id:
        flash("Accès refusé.", "error")
        return redirect(url_for("agent.dashboard"))

    contenu = (request.form.get("contenu") or "").strip()
    if not contenu:
        flash("Le commentaire est vide.", "error")
        return redirect(url_for("agent.detail_ticket", public_id=public_id))

    c = Comment(ticket_id=ticket.id, auteur_id=current_user.id, contenu=contenu)
    db.session.add(c)
    log_action(ticket.id, current_user.id, "commentaire_agent", None, contenu[:200])
    creer_notification(
        destinataire_id=ticket.demandeur_id,
        type_notif=NotificationType.COMMENTAIRE,
        message=f"L'équipe IT a commenté votre ticket « {ticket.titre} ».",
        ticket_id=ticket.id,
        titre="Mise à jour",
    )
    db.session.commit()
    flash("Commentaire ajouté.", "success")
    return redirect(url_for("agent.detail_ticket", public_id=public_id))


@bp.route("/tickets/<public_id>/statut", methods=["POST"])
@role_required(UserRole.AGENT_IT)
def changer_statut(public_id: str):
    ticket = Ticket.query.filter_by(public_id=public_id).first_or_404()
    if ticket.assignee_id != current_user.id:
        flash("Accès refusé.", "error")
        return redirect(url_for("agent.dashboard"))

    code_str = (request.form.get("statut_code") or "").strip()
    try:
        code = TicketStatusCode(code_str)
    except ValueError:
        flash("Statut invalide.", "error")
        return redirect(url_for("agent.detail_ticket", public_id=public_id))

    nouveau = TicketStatus.query.filter_by(code=code).first()
    if not nouveau:
        flash("Statut inconnu.", "error")
        return redirect(url_for("agent.detail_ticket", public_id=public_id))

    ancien = ticket.statut
    if ancien.id == nouveau.id:
        return redirect(url_for("agent.detail_ticket", public_id=public_id))

    if code not in (TicketStatusCode.EN_COURS, TicketStatusCode.RESOLU):
        flash("Vous ne pouvez passer le ticket qu'en « En cours » ou « Résolu ».", "error")
        return redirect(url_for("agent.detail_ticket", public_id=public_id))

    ticket.statut_id = nouveau.id
    ticket.date_mise_a_jour = datetime.utcnow()
    if code == TicketStatusCode.RESOLU:
        ticket.date_resolution = datetime.utcnow()

    log_action(
        ticket.id,
        current_user.id,
        "changement_statut",
        ancien.code.value,
        nouveau.code.value,
    )

    creer_notification(
        destinataire_id=ticket.demandeur_id,
        type_notif=NotificationType.STATUT_CHANGE,
        message=f"Votre ticket « {ticket.titre} » est maintenant : {nouveau.libelle}.",
        ticket_id=ticket.id,
        titre="Statut du ticket",
    )

    db.session.commit()
    flash("Statut mis à jour.", "success")
    return redirect(url_for("agent.detail_ticket", public_id=public_id))
