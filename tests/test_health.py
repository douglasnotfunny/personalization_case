from fastapi.testclient import TestClient

from app.main import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_metrics():
    with TestClient(app) as client:
        response = client.get("/metrics")

    assert response.status_code == 200

    data = response.json()

    assert "requests_total" in data
    assert "fallback_total" in data
    assert "errors_total" in data
    assert "average_latency_ms" in data