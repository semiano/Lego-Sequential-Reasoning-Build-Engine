import os
from pathlib import Path
import tempfile

import pytest
from fastapi.testclient import TestClient


TMP_ROOT = Path(tempfile.mkdtemp(prefix="leocad_toolkit_tests_"))
os.environ["DATA_DIR"] = str(TMP_ROOT / "data")
os.environ["DATABASE_URL"] = f"sqlite:///{(TMP_ROOT / 'test.db').as_posix()}"

from app.main import app  # noqa: E402
from app.core.db import init_db  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _init_db_once():
    init_db()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
