import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def fastapi_app():
    from app.main import app

    return app


@pytest.fixture
def client(fastapi_app):
    with TestClient(fastapi_app) as test_client:
        yield test_client
