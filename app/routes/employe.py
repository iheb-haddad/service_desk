from __future__ import annotations

from datetime import datetime, timedelta

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.decorators import role_required
from app.extensions import db
from app.models import (
    Attachment,
    Category,
    Comment,
    NotificationType,
    SatisfactionRating,
    Ticket,
    TicketHistory,
    TicketStatus,
    TicketStatusCode,
    Urgence,
    User,
    UserRole,
)
from app.services.history import log_action
from app.services.notifications import creer_notification
from app.services.priority import compute_priority
from app.services.similarity import apply_ai_suggestion
from app.utils.files import save_upload

bp = Blueprint("employe", __name__, url_prefix="/employe")


def _statut_par_code(code: TicketStatusCode) -> TicketStatus:
    s = TicketStatus.query.filter_by(code=code).first()
    if not s:
        raise RuntimeError(f"Statut manquant en base: {code}")
    return s


@bp.route("/")
@role_required(UserRole.EMPLOYE)
def dashboard():
    tickets = (
        Ticket.query.filter_by(demandeur_id=current_user.id)
        .order_by(Ticket.date_creation.desc())
        .limit(100)
        .all()
    )
    return render_template("employe/dashboard.html", tickets=tickets)


@bp.route("/tickets/nouveau", methods=["GET", "POST"])
@role_required(UserRole.EMPLOYE)
def nouveau_ticket():
    categories = Category.query.order_by(Category.nom).all()
    urgences = list(Urgence)

    if request.method == "POST":
        titre = (request.form.get("titre") or "").strip()
        description = (request.form.get("description") or "").strip()
        category_id = request.form.get("category_id", type=int)
        urgence_str = request.form.get("urgence") or Urgence.MOYENNE.value

        if not titre or not description or not category_id:
            flash("Titre, description et catégorie sont obligatoires.", "error")
            return render_template(
                "employe/ticket_form.html", categories=categories, urgences=urgences
            )

        try:
            urgence = Urgence(urgence_str)
        except ValueError:
            urgence = Urgence.MOYENNE

        cat = Category.query.get_or_404(category_id)
        priorite = compute_priority(urgence, cat)
        statut = _statut_par_code(TicketStatusCode.CREE)

        now = datetime.utcnow()
        echeance = now + timedelta(hours=cat.delai_sla_heures)

        ticket = Ticket(
            titre=titre,
            description=description,
            category_id=cat.id,
            urgence=urgence,
            priorite=priorite,
            statut_id=statut.id,
            demandeur_id=current_user.id,
            date_creation=now,
            date_echeance_sla=echeance,
        )
        db.session.add(ticket)
        db.session.flush()

        log_action(ticket.id, current_user.id, "creation", None, f"statut:{statut.code.value}")

        files = request.files.getlist("pieces_jointes")
        upload_root = current_app.config["UPLOAD_FOLDER"]
        allowed = current_app.config["ALLOWED_EXTENSIONS"]
        for f in files:
            saved = save_upload(f, upload_root, ticket.id, allowed)
            if not saved:
                continue
            nom_original, nom_stocke, taille = saved
            mime = f.mimetype or "application/octet-stream"
            att = Attachment(
                ticket_id=ticket.id,
                nom_fichier=nom_original,
                nom_stocke=nom_stocke,
                taille_octets=taille,
                type_mime=mime,
                uploadeur_id=current_user.id,
            )
            db.session.add(att)

        msg = f"Nouveau ticket : « {ticket.titre} » ({ticket.public_id[:8]})."

        for admin in User.query.filter_by(role=UserRole.ADMIN, actif=True).all():
            creer_notification(
                destinataire_id=admin.id,
                type_notif=NotificationType.TICKET_CREE,
                message=msg,
                ticket_id=ticket.id,
                titre="Nouvelle demande",
            )

        creer_notification(
            destinataire_id=current_user.id,
            type_notif=NotificationType.TICKET_CREE,
            message=f"Votre ticket « {ticket.titre} » a bien été enregistré.",
            ticket_id=ticket.id,
            titre="Confirmation",
        )

        db.session.commit()

        # La suggestion IA est calculée après création persistée du ticket.
        if apply_ai_suggestion(ticket):
            db.session.commit()

        flash("Ticket créé avec succès.", "success")
        return redirect(url_for("employe.detail_ticket", public_id=ticket.public_id))

    return render_template(
        "employe/ticket_form.html", categories=categories, urgences=urgences
    )


@bp.route("/tickets/<public_id>")
@role_required(UserRole.EMPLOYE)
def detail_ticket(public_id: str):
    ticket = Ticket.query.filter_by(public_id=public_id).first_or_404()
    if ticket.demandeur_id != current_user.id:
        flash("Ce ticket ne vous appartient pas.", "error")
        return redirect(url_for("employe.dashboard"))

    historique = (
        TicketHistory.query.filter_by(ticket_id=ticket.id)
        .order_by(TicketHistory.date_action.asc())
        .all()
    )

    return render_template(
        "employe/ticket_detail.html",
        ticket=ticket,
        historique=historique,
    )


@bp.route("/tickets/<public_id>/commentaire", methods=["POST"])
@role_required(UserRole.EMPLOYE)
def ajouter_commentaire(public_id: str):
    ticket = Ticket.query.filter_by(public_id=public_id).first_or_404()
    if ticket.demandeur_id != current_user.id:
        flash("Accès refusé.", "error")
        return redirect(url_for("employe.dashboard"))

    contenu = (request.form.get("contenu") or "").strip()
    if not contenu:
        flash("Le commentaire est vide.", "error")
        return redirect(url_for("employe.detail_ticket", public_id=public_id))

    c = Comment(ticket_id=ticket.id, auteur_id=current_user.id, contenu=contenu)
    db.session.add(c)
    log_action(ticket.id, current_user.id, "commentaire_employe", None, contenu[:200])
    if ticket.assignee_id:
        creer_notification(
            destinataire_id=ticket.assignee_id,
            type_notif=NotificationType.COMMENTAIRE,
            message=f"Nouveau commentaire sur « {ticket.titre} ».",
            ticket_id=ticket.id,
            titre="Commentaire employé",
        )
    db.session.commit()
    flash("Commentaire ajouté.", "success")
    return redirect(url_for("employe.detail_ticket", public_id=public_id))


@bp.route("/tickets/<public_id>/satisfaction", methods=["POST"])
@role_required(UserRole.EMPLOYE)
def satisfaction(public_id: str):
    ticket = Ticket.query.filter_by(public_id=public_id).first_or_404()
    if ticket.demandeur_id != current_user.id:
        flash("Accès refusé.", "error")
        return redirect(url_for("employe.dashboard"))

    statut_resolu = TicketStatus.query.filter_by(code=TicketStatusCode.RESOLU).first()
    if not statut_resolu or ticket.statut_id != statut_resolu.id:
        flash("Le ticket doit être résolu avant clôture et évaluation.", "error")
        return redirect(url_for("employe.detail_ticket", public_id=public_id))

    if ticket.satisfaction:
        flash("Vous avez déjà évalué ce ticket.", "info")
        return redirect(url_for("employe.detail_ticket", public_id=public_id))

    score = request.form.get("score", type=int)
    commentaire = (request.form.get("commentaire") or "").strip()
    if score is None or score < 1 or score > 5:
        flash("Veuillez choisir une note entre 1 et 5.", "error")
        return redirect(url_for("employe.detail_ticket", public_id=public_id))

    statut_ferme = _statut_par_code(TicketStatusCode.FERME)

    eval_row = SatisfactionRating(
        ticket_id=ticket.id,
        utilisateur_id=current_user.id,
        score=score,
        commentaire=commentaire or None,
    )
    db.session.add(eval_row)
    ticket.statut_id = statut_ferme.id
    ticket.date_resolution = ticket.date_resolution or datetime.utcnow()
    ticket.date_mise_a_jour = datetime.utcnow()
    log_action(
        ticket.id,
        current_user.id,
        "cloture_satisfaction",
        TicketStatusCode.RESOLU.value,
        TicketStatusCode.FERME.value,
    )
    if ticket.assignee_id:
        creer_notification(
            destinataire_id=ticket.assignee_id,
            type_notif=NotificationType.RESOLUTION,
            message=f"Ticket « {ticket.titre} » clôturé avec la note {score}/5.",
            ticket_id=ticket.id,
            titre="Évaluation reçue",
        )

    db.session.commit()
    flash("Merci pour votre retour. Le ticket est clôturé.", "success")
    return redirect(url_for("employe.detail_ticket", public_id=public_id))
