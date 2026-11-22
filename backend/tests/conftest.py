import os
import tempfile
from pathlib import Path

import pytest

# Banco isolado para os testes (definido antes de importar a aplicação)
_tmp = Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}"
os.environ["ADMIN_TOKEN"] = "token-de-teste"
os.environ["LLM_BASE_URL"] = ""
os.environ["LLM_MODEL"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.routers.assistant import chat_rate_limit  # noqa: E402
from app.security import rate_limit  # noqa: E402


@pytest.fixture()
def client():
    rate_limit.reset()
    chat_rate_limit.reset()
    with TestClient(app) as c:
        yield c
