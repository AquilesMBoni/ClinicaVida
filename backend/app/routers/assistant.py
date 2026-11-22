"""Rota do assistente virtual. As conversas NÃO são persistidas (LGPD)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..assistant.engine import Assistant, Knowledge
from ..config import settings
from ..database import get_db
from ..schemas import ChatRequest, ChatResponse
from ..security import RateLimiter

router = APIRouter(prefix="/api/assistant", tags=["assistente virtual"])

chat_rate_limit = RateLimiter(max(settings.rate_limit_per_minute, 1) * 2)


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(chat_rate_limit)])
def chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    assistant = Assistant(Knowledge.load(db), db=db)
    return assistant.reply(payload.message, payload.history)


@router.get("/status")
def assistant_status() -> dict:
    return {"online": True, "llm": settings.llm_enabled, "model": settings.llm_model or None}
