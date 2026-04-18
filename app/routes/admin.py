from __future__ import annotations

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.decorators import role_required
from app.extensions import db
from app.models import (
    NotificationType,
    Ticket,
    TicketHistory,
    TicketStatus,
    TicketStatusCode,
    User,
    UserRole,
)
from app.services.history import log_action
from app.services.notifications import creer_notification

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@role_required(UserRole.ADMIN)
def dashboard():
    total = Ticket.query.count()
    ouverts = (
        db.session.query(Ticket)
        .join(TicketStatus, Ticket.statut_id == TicketStatus.id)
        .filter(TicketStatus.code.in_([TicketStatusCode.CREE, TicketStatusCode.EN_COURS]))
        .count()
    )
    escalades = (
        db.session.query(Ticket)
        .join(TicketStatus, Ticket.statut_id == TicketStatus.id)
        .filter(TicketStatus.code == TicketStatusCode.ESCALADE)
        .count()
    )
    recents = Ticket.query.order_by(Ticket.date_creation.desc()).limit(12).all()
    users_count = User.query.filter_by(actif=True).count()
    return render_template(
        "admin/dashboard.html",
        total=total,
        ouverts=ouverts,
        escalades=escalades,
        recents=recents,
        users_count=users_count,
    )


@bp.route("/tickets")
@role_required(UserRole.ADMIN)
def liste_tickets():
    statut_filtre = request.args.get("statut")
    q = Ticket.query
    if statut_filtre:
        try:
            code = TicketStatusCode(statut_filtre)
            st = TicketStatus.query.filter_by(code=code).first()
            if st:
                q = q.filter(Ticket.statut_id == st.id)
        except ValueError:
            pass
    tickets = q.order_by(Ticket.date_creation.desc()).limit(200).all()
    statuts = TicketStatus.query.order_by(TicketStatus.id).all()
    return render_template("admin/tickets.html", tickets=tickets, statuts=statuts, statut_filtre=statut_filtre)


@bp.route("/tickets/<public_id>", methods=["GET", "POST"])
@role_required(UserRole.ADMIN)
def detail_ticket(public_id: str):
    ticket = Ticket.query.filter_by(public_id=public_id).first_or_404()
    agents = User.query.filter_by(role=UserRole.AGENT_IT, actif=True).order_by(User.nom).all()
    statuts = TicketStatus.query.order_by(TicketStatus.id).all()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "assigner":
            agent_id = request.form.get("agent_id", type=int)
            ancien_id = ticket.assignee_id

            if not agent_id:
                ticket.assignee_id = None
                ticket.date_mise_a_jour = datetime.utcnow()
                log_action(ticket.id, current_user.id, "assignation", str(ancien_id), "aucun")
                db.session.commit()
                flash("Assignation retirée.", "info")
                return redirect(url_for("admin.detail_ticket", public_id=public_id))

            agent = User.query.filter_by(id=agent_id, role=UserRole.AGENT_IT, actif=True).first()
            if not agent:
                flash("Agent introuvable.", "error")
                return redirect(url_for("admin.detail_ticket", public_id=public_id))

            ticket.assignee_id = agent.id
            en_cours = TicketStatus.query.filter_by(code=TicketStatusCode.EN_COURS).first()
            if en_cours and ticket.statut.code == TicketStatusCode.CREE:
                ticket.statut_id = en_cours.id
            ticket.date_mise_a_jour = datetime.utcnow()
            log_action(
                ticket.id,
                current_user.id,
                "assignation",
                str(ancien_id),
                str(agent.id),
            )
            creer_notification(
                destinataire_id=agent.id,
                type_notif=NotificationType.TICKET_ASSIGNE,
                message=f"Le ticket « {ticket.titre} » vous a été assigné.",
                ticket_id=ticket.id,
                titre="Nouvelle assignation",
            )
            creer_notification(
                destinataire_id=ticket.demandeur_id,
                type_notif=NotificationType.TICKET_ASSIGNE,
                message=f"Votre ticket « {ticket.titre} » a été pris en charge par {agent.full_name}.",
                ticket_id=ticket.id,
                titre="Assignation",
            )
            db.session.commit()
            flash("Ticket assigné à l'agent sélectionné.", "success")
            return redirect(url_for("admin.detail_ticket", public_id=public_id))

        if action == "statut":
            code_str = (request.form.get("statut_code") or "").strip()
            try:
                code = TicketStatusCode(code_str)
            except ValueError:
                flash("Statut invalide.", "error")
                return redirect(url_for("admin.detail_ticket", public_id=public_id))
            nouveau = TicketStatus.query.filter_by(code=code).first()
            if not nouveau:
                flash("Statut inconnu.", "error")
                return redirect(url_for("admin.detail_ticket", public_id=public_id))
            ancien = ticket.statut
            ticket.statut_id = nouveau.id
            ticket.date_mise_a_jour = datetime.utcnow()
            if code == TicketStatusCode.RESOLU:
                ticket.date_resolution = datetime.utcnow()
            log_action(
                ticket.id,
                current_user.id,
                "changement_statut_admin",
                ancien.code.value,
                nouveau.code.value,
            )
            creer_notification(
                destinataire_id=ticket.demandeur_id,
                type_notif=NotificationType.STATUT_CHANGE,
                message=f"Mise à jour : « {ticket.titre} » → {nouveau.libelle}.",
                ticket_id=ticket.id,
                titre="Statut du ticket",
            )
            if ticket.assignee_id:
                creer_notification(
                    destinataire_id=ticket.assignee_id,
                    type_notif=NotificationType.STATUT_CHANGE,
                    message=f"Statut mis à jour par l'administrateur : {nouveau.libelle}.",
                    ticket_id=ticket.id,
                    titre="Statut du ticket",
                )
            db.session.commit()
            flash("Statut mis à jour.", "success")
            return redirect(url_for("admin.detail_ticket", public_id=public_id))

    historique = (
        TicketHistory.query.filter_by(ticket_id=ticket.id)
        .order_by(TicketHistory.date_action.asc())
        .all()
    )
    return render_template(
        "admin/ticket_detail.html",
        ticket=ticket,
        agents=agents,
        statuts=statuts,
        historique=historique,
    )


@bp.route("/utilisateurs")
@role_required(UserRole.ADMIN)
def utilisateurs():
    users = User.query.order_by(User.role, User.nom).all()
    return render_template("admin/users.html", users=users)


@bp.route("/utilisateurs/nouveau", methods=["GET", "POST"])
@role_required(UserRole.ADMIN)
def nouvel_utilisateur():
    roles = list(UserRole)
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        nom = (request.form.get("nom") or "").strip()
        prenom = (request.form.get("prenom") or "").strip()
        role_str = (request.form.get("role") or "").strip()
        departement = (request.form.get("departement") or "").strip() or None
        telephone = (request.form.get("telephone") or "").strip() or None

        if not email or not password or not nom or not prenom:
            flash("Champs obligatoires manquants.", "error")
            return render_template("admin/user_form.html", roles=roles)
        try:
            role = UserRole(role_str)
        except ValueError:
            flash("Rôle invalide.", "error")
            return render_template("admin/user_form.html", roles=roles)

        if User.query.filter_by(email=email).first():
            flash("Cet e-mail existe déjà.", "error")
            return render_template("admin/user_form.html", roles=roles)

        u = User(
            email=email,
            nom=nom,
            prenom=prenom,
            role=role,
            departement=departement,
            telephone=telephone,
            actif=True,
        )
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        flash("Utilisateur créé.", "success")
        return redirect(url_for("admin.utilisateurs"))

    return render_template("admin/user_form.html", roles=roles)


@bp.route("/utilisateurs/<int:user_id>/toggle", methods=["POST"])
@role_required(UserRole.ADMIN)
def toggle_utilisateur(user_id: int):
    u = User.query.get_or_404(user_id)
    if u.id == current_user.id:
        flash("Vous ne pouvez pas désactiver votre propre compte.", "error")
        return redirect(url_for("admin.utilisateurs"))
    u.actif = not u.actif
    db.session.commit()
    flash("Compte mis à jour.", "success")
    return redirect(url_for("admin.utilisateurs"))
