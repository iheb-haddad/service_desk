from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from flask import current_app
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.models import AISuggestionStatus, Ticket, TicketStatusCode


@dataclass(frozen=True)
class TicketSuggestion:
    source_ticket_id: int
    score: float
    suggested_solution: str


def _normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def suggest_for_ticket(ticket: Ticket) -> Optional[TicketSuggestion]:
    if not current_app.config.get("AI_SIMILARITY_ENABLED", True):
        return None

    min_score = float(current_app.config.get("AI_SIMILARITY_MIN_SCORE", 0.30))
    same_category_only = bool(current_app.config.get("AI_SIMILARITY_SAME_CATEGORY_ONLY", True))
    max_corpus_tickets = int(current_app.config.get("AI_MAX_CORPUS_TICKETS", 500))

    query = Ticket.query.filter(
        Ticket.id != ticket.id,
        Ticket.solution.isnot(None),
        Ticket.solution != "",
        Ticket.statut.has(code=TicketStatusCode.RESOLU) | Ticket.statut.has(code=TicketStatusCode.FERME),
    ).order_by(Ticket.date_resolution.desc(), Ticket.date_creation.desc())

    if same_category_only:
        query = query.filter(Ticket.category_id == ticket.category_id)

    corpus = query.limit(max_corpus_tickets).all()
    if not corpus:
        return None

    current_text = _normalize_text(f"{ticket.titre} {ticket.description}")
    if not current_text:
        return None

    corpus_texts = [_normalize_text(f"{item.titre} {item.description}") for item in corpus]
    vectorizer = TfidfVectorizer()
    matrix = vectorizer.fit_transform([current_text] + corpus_texts)
    similarities = cosine_similarity(matrix[0:1], matrix[1:]).flatten()

    if similarities.size == 0:
        return None

    best_index = int(similarities.argmax())
    best_score = float(similarities[best_index])
    if best_score < min_score:
        return None

    source = corpus[best_index]
    if not source.solution:
        return None

    return TicketSuggestion(
        source_ticket_id=source.id,
        score=best_score,
        suggested_solution=source.solution,
    )


def apply_ai_suggestion(ticket: Ticket) -> bool:
    suggestion = suggest_for_ticket(ticket)
    if not suggestion:
        ticket.ai_source_ticket_id = None
        ticket.ai_similarity_score = None
        ticket.ai_suggested_solution = None
        ticket.ai_suggestion_status = AISuggestionStatus.NONE
        return False

    ticket.ai_source_ticket_id = suggestion.source_ticket_id
    ticket.ai_similarity_score = suggestion.score
    ticket.ai_suggested_solution = suggestion.suggested_solution
    ticket.ai_suggestion_status = AISuggestionStatus.PENDING
    return True
