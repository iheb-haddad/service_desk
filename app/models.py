from __future__ import annotations

import enum
import uuid
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    EMPLOYE = "employe"
    AGENT_IT = "agent_it"


class Urgence(str, enum.Enum):
    BASSE = "basse"
    MOYENNE = "moyenne"
    HAUTE = "haute"
    CRITIQUE = "critique"


class Priorite(str, enum.Enum):
    FAIBLE = "faible"
    MOYENNE = "moyenne"
    HAUTE = "haute"
    CRITIQUE = "critique"


class TicketStatusCode(str, enum.Enum):
    CREE = "cree"
    EN_COURS = "en_cours"
    RESOLU = "resolu"
    FERME = "ferme"
    ESCALADE = "escalade"


class NotificationType(str, enum.Enum):
    TICKET_CREE = "ticket_cree"
    TICKET_ASSIGNE = "ticket_assigne"
    STATUT_CHANGE = "statut_change"
    COMMENTAIRE = "commentaire"
    ESCALADE = "escalade"
    RESOLUTION = "resolution"


class AISuggestionStatus(str, enum.Enum):
    NONE = "none"
    PENDING = "pending"
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"


class User(UserMixin, db.Model):
    __tablename__ = "utilisateurs"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    role = db.Column(db.Enum(UserRole), nullable=False, index=True)
    departement = db.Column(db.String(120))
    telephone = db.Column(db.String(40))
    actif = db.Column(db.Boolean, default=True, nullable=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    derniere_connexion = db.Column(db.DateTime)

    tickets_crees = db.relationship(
        "Ticket",
        foreign_keys="Ticket.demandeur_id",
        back_populates="demandeur",
        lazy="dynamic",
    )
    tickets_assignes = db.relationship(
        "Ticket",
        foreign_keys="Ticket.assignee_id",
        back_populates="assignee",
        lazy="dynamic",
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self) -> str:
        return f"{self.prenom} {self.nom}".strip()


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(120), unique=True, nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    delai_sla_heures = db.Column(db.Integer, nullable=False, default=48)
    poids_priorite = db.Column(db.Integer, nullable=False, default=2)

    tickets = db.relationship("Ticket", back_populates="category", lazy="dynamic")


class TicketStatus(db.Model):
    __tablename__ = "statuts_ticket"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.Enum(TicketStatusCode), unique=True, nullable=False)
    libelle = db.Column(db.String(80), nullable=False)

    tickets = db.relationship("Ticket", back_populates="statut", lazy="dynamic")


class Ticket(db.Model):
    __tablename__ = "tickets"

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    titre = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    urgence = db.Column(db.Enum(Urgence), nullable=False, default=Urgence.MOYENNE)
    priorite = db.Column(db.Enum(Priorite), nullable=False, default=Priorite.MOYENNE)

    statut_id = db.Column(db.Integer, db.ForeignKey("statuts_ticket.id"), nullable=False)
    demandeur_id = db.Column(db.Integer, db.ForeignKey("utilisateurs.id"), nullable=False)
    assignee_id = db.Column(db.Integer, db.ForeignKey("utilisateurs.id"), nullable=True)

    date_creation = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    date_mise_a_jour = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    date_echeance_sla = db.Column(db.DateTime)
    date_resolution = db.Column(db.DateTime)
    escalade_declenchee = db.Column(db.Boolean, default=False, nullable=False)
    solution = db.Column(db.Text)
    ai_source_ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=True)
    ai_similarity_score = db.Column(db.Float)
    ai_suggested_solution = db.Column(db.Text)
    ai_suggestion_status = db.Column(db.Enum(AISuggestionStatus), nullable=False, default=AISuggestionStatus.NONE)

    category = db.relationship("Category", back_populates="tickets")
    statut = db.relationship("TicketStatus", back_populates="tickets")
    demandeur = db.relationship("User", foreign_keys=[demandeur_id], back_populates="tickets_crees")
    assignee = db.relationship("User", foreign_keys=[assignee_id], back_populates="tickets_assignes")
    ai_source_ticket = db.relationship("Ticket", remote_side=[id], foreign_keys=[ai_source_ticket_id], uselist=False)

    commentaires = db.relationship(
        "Comment",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="Comment.date_creation",
    )
    pieces_jointes = db.relationship(
        "Attachment",
        back_populates="ticket",
        cascade="all, delete-orphan",
    )
    notifications = db.relationship("Notification", back_populates="ticket", cascade="all, delete-orphan")
    historique = db.relationship(
        "TicketHistory",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="TicketHistory.date_action",
    )
    satisfaction = db.relationship(
        "SatisfactionRating",
        back_populates="ticket",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Comment(db.Model):
    __tablename__ = "commentaires"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False)
    auteur_id = db.Column(db.Integer, db.ForeignKey("utilisateurs.id"), nullable=False)
    contenu = db.Column(db.Text, nullable=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    ticket = db.relationship("Ticket", back_populates="commentaires")
    auteur = db.relationship("User")


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    destinataire_id = db.Column(db.Integer, db.ForeignKey("utilisateurs.id"), nullable=False, index=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=True)
    type_notif = db.Column(db.Enum(NotificationType), nullable=False)
    titre = db.Column(db.String(200))
    message = db.Column(db.Text, nullable=False)
    lue = db.Column(db.Boolean, default=False, nullable=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    destinataire = db.relationship("User", foreign_keys=[destinataire_id])
    ticket = db.relationship("Ticket", back_populates="notifications")


class TicketHistory(db.Model):
    __tablename__ = "historique_tickets"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey("utilisateurs.id"), nullable=True)
    action = db.Column(db.String(120), nullable=False)
    ancienne_valeur = db.Column(db.Text)
    nouvelle_valeur = db.Column(db.Text)
    date_action = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    ticket = db.relationship("Ticket", back_populates="historique")
    utilisateur = db.relationship("User")


class Attachment(db.Model):
    __tablename__ = "pieces_jointes"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False)
    nom_fichier = db.Column(db.String(255), nullable=False)
    nom_stocke = db.Column(db.String(255), nullable=False)
    taille_octets = db.Column(db.Integer)
    type_mime = db.Column(db.String(120))
    uploadeur_id = db.Column(db.Integer, db.ForeignKey("utilisateurs.id"), nullable=False)
    date_upload = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    ticket = db.relationship("Ticket", back_populates="pieces_jointes")
    uploadeur = db.relationship("User")


class SatisfactionRating(db.Model):
    __tablename__ = "evaluations_satisfaction"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False, unique=True)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey("utilisateurs.id"), nullable=False)
    score = db.Column(db.Integer, nullable=False)  # 1-5
    commentaire = db.Column(db.Text)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    ticket = db.relationship("Ticket", back_populates="satisfaction")
    utilisateur = db.relationship("User")
