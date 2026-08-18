from fastapi.testclient import TestClient

from app.main import app


def test_recommendations_known_user():
    with TestClient(app) as client:
        user_id = app.state.feature_df["user_id"].iloc[0]

        response = client.get(f"/recommendations/{user_id}")

    assert response.status_code == 200

    payload = response.json()

    assert payload["user_id"] == user_id
    assert payload["fallback"] is False
    assert len(payload["recommendations"]) == 10

    for recommendation in payload["recommendations"]:
        assert "product_id" in recommendation
        assert "score" in recommendation
        assert 0 <= recommendation["score"] <= 1


def test_recommendations_are_sorted_by_score():
    with TestClient(app) as client:
        user_id = app.state.feature_df["user_id"].iloc[0]

        response = client.get(f"/recommendations/{user_id}")

    recommendations = response.json()["recommendations"]

    scores = [item["score"] for item in recommendations]

    assert scores == sorted(scores, reverse=True)


def test_recommendations_are_sorted_by_score():
    with TestClient(app) as client:
        user_id = app.state.feature_df["user_id"].iloc[0]

        response = client.get(f"/recommendations/{user_id}")

    recommendations = response.json()["recommendations"]

    scores = [item["score"] for item in recommendations]

    assert scores == sorted(scores, reverse=True)


def test_cold_start_uses_most_popular_products():
    with TestClient(app) as client:
        expected = (
            app.state.products
            .sort_values("popularity_score", ascending=False)
            .head(10)
        )

        response = client.get(
            "/recommendations/cold_start_user"
        )

    recommendations = response.json()["recommendations"]

    expected_ids = expected["product_id"].tolist()
    actual_ids = [item["product_id"] for item in recommendations]

    assert actual_ids == expected_ids

def test_recommendations_end_to_end():
    with TestClient(app) as client:
        user_id = app.state.feature_df["user_id"].iloc[0]

        response = client.get(
            f"/recommendations/{user_id}"
        )

    assert response.status_code == 200

    payload = response.json()

    assert payload["user_id"] == user_id
    assert payload["fallback"] is False
    assert len(payload["recommendations"]) == 10

    scores = [
        item["score"]
        for item in payload["recommendations"]
    ]

    assert scores == sorted(scores, reverse=True)