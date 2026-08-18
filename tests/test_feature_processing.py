import pandas as pd

from app.feature_processing import build_feature_dataset


def test_feature_processing():

    events = pd.DataFrame(
        {
            "user_id": ["u1", "u1", "u1"],
            "product_id": ["p1", "p1", "p2"],
            "event_type": ["view", "click", "view"],
            "timestamp": [
                "2026-01-01",
                "2026-01-02",
                "2026-01-03",
            ],
        }
    )

    products = pd.DataFrame(
        {
            "product_id": ["p1", "p2"],
            "category": ["books", "electronics"],
            "price": [100.0, 200.0],
            "avg_rating": [4.5, 4.0],
            "popularity_score": [0.8, 0.5],
        }
    )

    result = build_feature_dataset(
        events,
        products,
    )

    u1_p1 = result[
        (result["user_id"] == "u1")
        & (result["product_id"] == "p1")
    ].iloc[0]

    assert u1_p1["interactions"] == 2
    assert u1_p1["user_affinity_match"] == 1

    u1_p2 = result[
        (result["user_id"] == "u1")
        & (result["product_id"] == "p2")
    ].iloc[0]

    assert u1_p2["interactions"] == 1
    assert u1_p2["user_affinity_match"] == 0