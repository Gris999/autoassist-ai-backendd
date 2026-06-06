from fastapi.testclient import TestClient


def test_app_imports_correctly():
    from app.main import app

    assert app is not None


def test_testclient_can_be_created(fastapi_app):
    client = TestClient(fastapi_app)
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ia_endpoint_requires_auth(client):
    response = client.get("/api/v1/inteligencia/incidentes/1/evidencias")

    assert response.status_code in {401, 403}
