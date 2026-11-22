"""Utilidades de segurança: limite de requisições por IP e token administrativo."""
from __future__ import annotations

import secrets
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request, status

from .config import settings


class RateLimiter:
    """Janela deslizante em memória (suficiente para um projeto de portfólio em instância única)."""

    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def __call__(self, request: Request) -> None:
        if self.limit <= 0:
            return
        key = request.client.host if request.client else "anon"
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitas requisições em sequência. Aguarde alguns segundos e tente novamente.",
            )
        hits.append(now)

    def reset(self) -> None:
        self._hits.clear()


rate_limit = RateLimiter(settings.rate_limit_per_minute)


def require_admin(x_admin_token: str = Header(default="")) -> None:
    if not secrets.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token administrativo inválido.")
