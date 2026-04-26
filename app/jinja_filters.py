"""Filtres Jinja partagés (dates UTC ISO, libellés timeline)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.models import TicketStatusCode


def utc_iso_datetime(value: datetime | None) -> str:
    """Naive datetimes en base sont interprétées comme UTC (cohérent avec datetime.utcnow)."""
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def timeline_event_label(h) -> str:
    """Libellé français pour une ligne d’historique ticket (code + cas particuliers)."""
    code = (h.action or "").strip()
    nv = (getattr(h, "nouvelle_valeur", None) or "").strip()
    av = (getattr(h, "ancienne_valeur", None) or "").strip()

    if code == "changement_statut" and nv == TicketStatusCode.RESOLU.value:
        return "Résolution du ticket"
    if code == "changement_statut":
        return "Changement de statut"

    labels: dict[str, str] = {
        "creation": "Création du ticket",
        "assignation": "Assignation",
        "resolution": "Résolution du ticket",
        "changement_statut_admin": "Changement de statut (administration)",
        "commentaire_agent": "Commentaire de l’équipe IT",
        "commentaire_employe": "Commentaire du demandeur",
        "ia_suggestion_accept": "Suggestion IA acceptée",
        "ia_suggestion_edit": "Solution enregistrée (suggestion IA modifiée)",
        "ia_suggestion_reject": "Suggestion IA rejetée",
        "cloture_satisfaction": "Clôture après évaluation",
        "escalade_automatique": "Escalade automatique (dépassement SLA)",
    }
    return labels.get(code, code.replace("_", " ").title())


def register_template_filters(app) -> None:
    app.jinja_env.filters["utc_iso_datetime"] = utc_iso_datetime
    app.jinja_env.filters["timeline_event_label"] = timeline_event_label
