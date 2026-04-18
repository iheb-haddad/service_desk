"""
Initialise la base MySQL : tables + données de démonstration.
À exécuter une fois après création de la base vide.
"""

from app import create_app
from app.extensions import db
from app.models import (
    Category,
    TicketStatus,
    TicketStatusCode,
    User,
    UserRole,
)


def seed():
    # Statuts
    statuts = [
        (TicketStatusCode.CREE, "Créé"),
        (TicketStatusCode.EN_COURS, "En cours de traitement"),
        (TicketStatusCode.RESOLU, "Résolu"),
        (TicketStatusCode.FERME, "Fermé"),
        (TicketStatusCode.ESCALADE, "Escaladé"),
    ]
    for code, lib in statuts:
        if not TicketStatus.query.filter_by(code=code).first():
            db.session.add(TicketStatus(code=code, libelle=lib))

    # Catégories (SLA en heures, poids pour priorité)
    cats = [
        ("Accès & sécurité", "acces-securite", 24, 3),
        ("Infrastructure", "infrastructure", 48, 3),
        ("Applicatif métier", "applicatif", 72, 2),
        ("Matériel & poste de travail", "materiel", 48, 2),
        ("Autre demande", "autre", 48, 1),
    ]
    for nom, slug, sla, poids in cats:
        if not Category.query.filter_by(slug=slug).first():
            db.session.add(
                Category(
                    nom=nom,
                    slug=slug,
                    delai_sla_heures=sla,
                    poids_priorite=poids,
                )
            )

    # Comptes démo (à modifier en production)
    users = [
        ("admin@bh.tn", "Admin", "BH", UserRole.ADMIN, "Admin123!"),
        ("employe@bh.tn", "Salah", "Ben Ali", UserRole.EMPLOYE, "Employe123!"),
        ("agent@bh.tn", "Sonia", "IT", UserRole.AGENT_IT, "Agent123!"),
    ]
    for email, prenom, nom, role, pwd in users:
        if not User.query.filter_by(email=email).first():
            u = User(
                email=email,
                nom=nom,
                prenom=prenom,
                role=role,
                departement="Direction générale",
                telephone="+216 71 000 000",
                actif=True,
            )
            u.set_password(pwd)
            db.session.add(u)

    db.session.commit()
    print("OK — Tables et données initiales prêtes.")
    print("Comptes démo :")
    print("  admin@bh.tn   / Admin123!")
    print("  employe@bh.tn / Employe123!")
    print("  agent@bh.tn   / Agent123!")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
        seed()
