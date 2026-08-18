import logging
import pandas as pd

logger = logging.getLogger("personalization")

def user_empty(products: pd.DataFrame, user_id: str) -> dict:
    recommendations = (products.sort_values("popularity_score",ascending=False).head(10))
    return {
        "user_id": user_id,
        "recommendations": (recommendations[["product_id", "popularity_score"]]
            .rename(columns={"popularity_score": "score"})
            .to_dict(orient="records")
        ),
        "fallback": True,
    }
