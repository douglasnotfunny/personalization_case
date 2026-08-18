import pandas as pd
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cold_start_returns_popularity_fallback():
    products = pd.DataFrame(
        {
            "product_id": ["p1", "p2", "p3", "p4", "p5"],
            "popularity_score": [0.9, 0.8, 0.7, 0.6, 0.5],
        }
    )

    feature_df = pd.DataFrame(
        {
            "user_id": ["u1"],
            "product_id": ["p1"],
            "interactions": [1],
            "user_affinity_match": [1],
        }
    )

    app.state.feature_df = feature_df
    app.state.products = products
    app.state.model = None
    app.state.scaler = None
    app.state.feature_cols = ["interactions", "user_affinity_match"]

    response = client.get("/recommendations/unknown_user")

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] == "unknown_user"
    assert payload["fallback"] is True
    assert payload["recommendations"][0]["product_id"] == "p1"
    assert payload["recommendations"][0]["score"] == 0.9