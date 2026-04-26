from __future__ import annotations

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.decorators import role_required
from app.extensions import db
from app.models import (
    AISuggestionStatus,
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


def _ticket_resolu_row() -> TicketStatus | None:
    return TicketStatus.query.filter_by(code=TicketStatusCode.RESOLU).first()


def _appliquer_solution_et_resoudre(ticket: Ticket, solution: str) -> bool:
    """
    Enregistre la solution et passe le ticket en « Résolu » si ce n'est pas déjà fermé.
    Retourne False si le ticket est fermé (aucune modification statut).
    """
    texte = solution.strip()
    if not texte:
        return True

    if ticket.statut.code == TicketStatusCode.FERME:
        return False

    statut_resolu = _ticket_resolu_row()
    if not statut_resolu:
        raise RuntimeError("Statut « résolu » absent en base.")

    ancien = ticket.statut
    ticket.solution = texte
    ticket.date_mise_a_jour = datetime.utcnow()

    if ancien.code != TicketStatusCode.RESOLU:
        ticket.statut_id = statut_resolu.id
        ticket.date_resolution = datetime.utcnow()
        log_action(
            ticket.id,
            current_user.id,
            "resolution",
            ancien.code.value,
            TicketStatusCode.RESOLU.value,
        )
        creer_notification(
            destinataire_id=ticket.demandeur_id,
            type_notif=NotificationType.STATUT_CHANGE,
            message=f"Votre ticket « {ticket.titre} » est maintenant : {statut_resolu.libelle}.",
            ticket_id=ticket.id,
            titre="Statut du ticket",
        )

    return True


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
    return render_template(
        "agent/ticket_detail.html",
        ticket=ticket,
        historique=historique,
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

    solution = (request.form.get("solution") or "").strip()
    if not solution:
        flash("Veuillez renseigner une solution pour enregistrer.", "error")
        return redirect(url_for("agent.detail_ticket", public_id=public_id))

    ancien = ticket.statut
    deja_resolu = ancien.code == TicketStatusCode.RESOLU
    if not _appliquer_solution_et_resoudre(ticket, solution):
        flash("Ce ticket est clôturé ; la solution ne peut pas être enregistrée.", "error")
        return redirect(url_for("agent.detail_ticket", public_id=public_id))

    db.session.commit()
    flash(
        "Solution enregistrée ; le ticket est marqué comme résolu."
        if not deja_resolu
        else "Solution mise à jour.",
        "success",
    )
    return redirect(url_for("agent.detail_ticket", public_id=public_id))


@bp.route("/tickets/<public_id>/ai-suggestion/accept", methods=["POST"])
@role_required(UserRole.AGENT_IT)
def accept_ai_suggestion(public_id: str):
    ticket = Ticket.query.filter_by(public_id=public_id).first_or_404()
    if ticket.assignee_id != current_user.id:
        flash("Accès refusé.", "error")
        return redirect(url_for("agent.dashboard"))

    suggestion = (ticket.ai_suggested_solution or "").strip()
    if not suggestion:
        flash("Aucune suggestion IA disponible.", "error")
        return redirect(url_for("agent.detail_ticket", public_id=public_id))

    if ticket.statut.code == TicketStatusCode.FERME:
        flash("Ce ticket est clôturé.", "error")
        return redirect(url_for("agent.detail_ticket", public_id=public_id))

    deja_resolu = ticket.statut.code == TicketStatusCode.RESOLU
    ticket.ai_suggestion_status = AISuggestionStatus.ACCEPTED
    if not _appliquer_solution_et_resoudre(ticket, suggestion):
        flash("Ce ticket est clôturé.", "error")
        return redirect(url_for("agent.detail_ticket", public_id=public_id))

    db.session.add(Comment(ticket_id=ticket.id, auteur_id=current_user.id, contenu=suggestion))
    log_action(ticket.id, current_user.id, "ia_suggestion_accept", None, suggestion[:200])

    db.session.commit()
    flash(
        "Suggestion IA validée ; le ticket est marqué comme résolu."
        if not deja_resolu
        else "Suggestion IA validée et enregistrée.",
        "success",
    )
    return redirect(url_for("agent.detail_ticket", public_id=public_id))


@bp.route("/tickets/<public_id>/ai-suggestion/edit", methods=["POST"])
@role_required(UserRole.AGENT_IT)
def edit_ai_suggestion(public_id: str):
    ticket = Ticket.query.filter_by(public_id=public_id).first_or_404()
    if ticket.assignee_id != current_user.id:
        flash("Accès refusé.", "error")
        return redirect(url_for("agent.dashboard"))

    edited_solution = (request.form.get("edited_solution") or "").strip()
    if not edited_solution:
        flash("La solution modifiée est vide.", "error")
        return redirect(url_for("agent.detail_ticket", public_id=public_id))

    if ticket.statut.code == TicketStatusCode.FERME:
        flash("Ce ticket est clôturé.", "error")
        return redirect(url_for("agent.detail_ticket", public_id=public_id))

    deja_resolu = ticket.statut.code == TicketStatusCode.RESOLU
    ticket.ai_suggestion_status = AISuggestionStatus.EDITED
    if not _appliquer_solution_et_resoudre(ticket, edited_solution):
        flash("Ce ticket est clôturé.", "error")
        return redirect(url_for("agent.detail_ticket", public_id=public_id))

    db.session.add(Comment(ticket_id=ticket.id, auteur_id=current_user.id, contenu=edited_solution))
    log_action(ticket.id, current_user.id, "ia_suggestion_edit", None, edited_solution[:200])

    db.session.commit()
    flash(
        "Solution enregistrée ; le ticket est marqué comme résolu."
        if not deja_resolu
        else "Suggestion IA modifiée et enregistrée.",
        "success",
    )
    return redirect(url_for("agent.detail_ticket", public_id=public_id))


@bp.route("/tickets/<public_id>/ai-suggestion/reject", methods=["POST"])
@role_required(UserRole.AGENT_IT)
def reject_ai_suggestion(public_id: str):
    ticket = Ticket.query.filter_by(public_id=public_id).first_or_404()
    if ticket.assignee_id != current_user.id:
        flash("Accès refusé.", "error")
        return redirect(url_for("agent.dashboard"))

    ticket.ai_suggestion_status = AISuggestionStatus.REJECTED
    ticket.date_mise_a_jour = datetime.utcnow()
    log_action(ticket.id, current_user.id, "ia_suggestion_reject", None, "rejected")

    db.session.commit()
    flash("Suggestion IA rejetée.", "info")
    return redirect(url_for("agent.detail_ticket", public_id=public_id))
