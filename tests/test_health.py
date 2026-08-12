from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ready_status() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_preview_applies_allowlisted_operation() -> None:
    response = client.get(
        "/preview",
        params={"operation": "uppercase", "text": "Feiyu"},
    )

    assert response.status_code == 200
    assert response.json() == {"output": "FEIYU"}


def test_preview_rejects_unknown_operation() -> None:
    response = client.get(
        "/preview",
        params={"operation": "shell", "text": "whoami"},
    )

    assert response.status_code == 422
