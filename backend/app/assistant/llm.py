"""Integração opcional com um LLM compatível com a API da OpenAI (Ollama, LM Studio, OpenAI...).

Só é chamado quando as regras e o FAQ não encontram resposta. Qualquer falha (sem configuração,
timeout, erro HTTP) devolve None e o assistente segue com a resposta padrão.
"""
from __future__ import annotations

import logging

import httpx

from ..config import settings
from ..schemas import ChatTurn

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """Você é a Vida, assistente virtual da Clínica Vida (projeto demonstrativo).
Regras obrigatórias:
- Responda em português do Brasil, de forma cordial e em no máximo 4 frases curtas.
- Use SOMENTE as informações da clínica abaixo. Se não souber, diga que a recepção pode ajudar.
- Nunca faça diagnósticos, nunca indique medicamentos ou doses e nunca interprete exames.
- Em sinais de emergência, oriente ligar para o SAMU (192) ou procurar um pronto-socorro.
- Não invente preços, horários, convênios ou profissionais.
- Peça para o usuário não compartilhar dados de saúde no chat (LGPD).

Informações da clínica:
{context}"""


def ask(message: str, history: list[ChatTurn], context: str) -> str | None:
    if not settings.llm_enabled:
        return None

    messages = [{"role": "system", "content": SYSTEM_PROMPT.format(context=context)}]
    messages += [{"role": t.role, "content": t.content} for t in history[-6:]]
    messages.append({"role": "user", "content": message})

    headers = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"

    try:
        response = httpx.post(
            settings.llm_base_url.rstrip("/") + "/chat/completions",
            json={"model": settings.llm_model, "messages": messages, "temperature": 0.3, "max_tokens": 300},
            headers=headers,
            timeout=settings.llm_timeout,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        return content or None
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        log.warning("LLM indisponível, usando resposta padrão: %s", exc)
        return None
