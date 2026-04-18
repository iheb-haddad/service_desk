"""Règles de priorisation automatique (urgence × catégorie)."""

from __future__ import annotations

from app.models import Category, Priorite, Urgence

# Score d'urgence utilisé dans la matrice
URGENCE_SCORE: dict[Urgence, int] = {
    Urgence.BASSE: 1,
    Urgence.MOYENNE: 2,
    Urgence.HAUTE: 3,
    Urgence.CRITIQUE: 4,
}


def compute_priority(urgence: Urgence, category: Category) -> Priorite:
    """
    Combine l'urgence déclarée et le poids métier de la catégorie.
    Plus le score est élevé, plus la priorité calculée est haute.
    """
    u = URGENCE_SCORE.get(urgence, 2)
    poids = category.poids_priorite or 2
    score = u * 2 + poids

    if score <= 4:
        return Priorite.FAIBLE
    if score <= 7:
        return Priorite.MOYENNE
    if score <= 10:
        return Priorite.HAUTE
    return Priorite.CRITIQUE
