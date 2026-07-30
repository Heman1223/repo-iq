"""Question answering endpoint (/ask)."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from app.models.schemas import AskRequest, AskResponse
from app.services.rag_service import rag_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@router.post("/ask", response_model=AskResponse, summary="Ask a question about a repository")
def ask(payload: AskRequest) -> AskResponse:
    """Answer a natural-language question using only retrieved repository context.

    Declared as a synchronous handler on purpose: embedding and the Gemini call
    are blocking, so FastAPI runs this in its worker threadpool and the event
    loop stays free for status polling.
    """
    logger.info("Q[%s]: %s", payload.repo_id, payload.question[:160])
    return rag_service.answer_question(payload)
