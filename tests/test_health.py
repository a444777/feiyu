from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ready_status() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_preview_route_is_registered() -> None:
    paths = {route.path for route in app.routes}

    assert "/preview" in paths
