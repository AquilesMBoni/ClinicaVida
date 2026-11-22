"""Normalização de texto em português para o motor de intenções."""
from __future__ import annotations

import re
import unicodedata

STOPWORDS = {
    "a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "da", "do", "das", "dos", "e", "em", "no", "na",
    "nos", "nas", "para", "pra", "pro", "por", "com", "que", "qual", "quais", "se", "me", "eu", "voce",
    "voces", "vcs", "vc", "ai", "tem", "ter", "ha", "sao", "ser", "esta", "estao", "sobre", "como", "mais",
    "meu", "minha", "seu", "sua", "isso", "esse", "essa", "ao", "aos", "ou", "la", "aqui", "gostaria",
    "queria", "quero", "poderia", "pode", "posso", "saber", "favor", "ola", "oi",
}


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def normalize(text: str) -> str:
    text = strip_accents(text.lower())
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokens(text: str) -> list[str]:
    return [t for t in normalize(text).split() if t not in STOPWORDS and len(t) > 1]


def contains_any(normalized: str, terms: list[str] | tuple[str, ...] | set[str]) -> bool:
    """Procura termos inteiros (palavras ou expressões) no texto já normalizado."""
    padded = f" {normalized} "
    return any(f" {normalize(term)} " in padded for term in terms)


def contains_prefix(normalized: str, prefixes: tuple[str, ...]) -> bool:
    """Procura palavras que começam com algum prefixo (ex.: 'agend' → agendar, agendamento)."""
    return any(word.startswith(prefixes) for word in normalized.split())
