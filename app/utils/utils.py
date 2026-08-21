import logging
import pandas as pd
import pickle

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


def load_model():
    with open(f"model/model.pkl", "rb") as file:
            artifact = pickle.load(file)
    
    model = artifact["model"]
    scaler = artifact["scaler"]
    feature_cols = artifact["feature_cols"]
    
    logger.info(
        "model_loaded features=%s",
        feature_cols,
    )

    return {
        "model": model,
        "scaler": scaler,
        "feature_cols": feature_cols 
    }