"""Configurações da aplicação lidas de variáveis de ambiente (com padrões seguros para desenvolvimento)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent          # .../backend
PROJECT_DIR = BASE_DIR.parent                               # .../ClinicaVida
FRONTEND_DIR = PROJECT_DIR / "frontend"


def _load_dotenv(path: Path) -> None:
    """Carrega um .env simples (CHAVE=valor) sem depender de bibliotecas externas."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")


def _csv(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str = "Clínica Vida API"
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'clinicavida.db'}")
    cors_origins: list[str] = field(
        default_factory=lambda: _csv(
            "CORS_ORIGINS",
            "http://localhost:5500,http://127.0.0.1:5500,http://localhost:8000,http://127.0.0.1:8000",
        )
    )
    # Token simples para a rota administrativa de listagem de pré-agendamentos
    admin_token: str = os.getenv("ADMIN_TOKEN", "troque-este-token")

    # LLM opcional (qualquer endpoint compatível com OpenAI: Ollama, LM Studio, OpenAI...)
    llm_base_url: str = os.getenv("LLM_BASE_URL", "")
    llm_model: str = os.getenv("LLM_MODEL", "")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_timeout: float = float(os.getenv("LLM_TIMEOUT", "20"))

    # Limite de requisições por IP (por minuto) nas rotas de escrita
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_base_url and self.llm_model)


settings = Settings()
