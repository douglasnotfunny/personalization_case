import logging
import time
import pickle
from contextlib import asynccontextmanager

import pandas as pd
from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse

from app.feature_processing import build_feature_dataset
from app.metrics import record_request, record_error, get_metrics
from app.logging_config import configure_logging
from app.utils.utils import user_empty, load_model

configure_logging()

logger = logging.getLogger("personalization")

app = FastAPI(
    title="Personalization API"
)

@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    record_error()

    logger.exception(
        "application_error path=%s",
        request.url.path,
    )

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("feature_processing_started")

    events = pd.read_csv("data/events.csv")
    products = pd.read_csv("data/products.csv")

    logger.info(
        "datasets_loaded events=%s products=%s",
        len(events),
        len(products),
    )

    feature_df = build_feature_dataset(
        events,
        products,
    )

    logger.info(
        "feature_processing_completed users=%s products=%s rows=%s",
        feature_df["user_id"].nunique(),
        feature_df["product_id"].nunique(),
        len(feature_df),
    )

    load_model_recommendation = load_model()
    feature_cols = load_model_recommendation["feature_cols"]

    missing_features = set(feature_cols) - set(feature_df.columns)

    if missing_features:
        raise ValueError(
            f"Missing model features: {missing_features}"
        )

    app.state.feature_df = feature_df
    app.state.products = products
    app.state.model = load_model_recommendation["model"]
    app.state.scaler = load_model_recommendation["scaler"]
    app.state.feature_cols = feature_cols

    yield

app = FastAPI(
    title="Personalization API",
    description="Recommendation service",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
def root():
    return {"message": "Hello World"}


@app.get("/health")
def health():
    return {"status": "ok"}



@app.get("/recommendations/{user_id}")
def get_recommendations(user_id: str):
    start_time = time.perf_counter()

    feature_df = app.state.feature_df
    products = app.state.products
    model = app.state.model
    scaler = app.state.scaler
    feature_cols = app.state.feature_cols

    user_df = feature_df[feature_df["user_id"] == user_id].copy()

    if user_df.empty:
        latency_ms = (time.perf_counter() - start_time) * 1000
        logger.info("recommendation_request " 
                    "user_id=%s latency_ms=%.2f fallback=%s",
                    user_id, latency_ms, "True"
        )

        record_request(
            latency_ms=latency_ms,
            fallback=True,
        )
        return user_empty(products=products, user_id=user_id)

    X = user_df[feature_cols]
    X_scaled = scaler.transform(X.to_numpy())
    scores = model.predict_proba(X_scaled)[:, 1]
    user_df["score"] = scores

    recommendations = (user_df.sort_values("score",ascending=False).head(10))

    latency_ms = (time.perf_counter() - start_time) * 1000
    logger.info("recommendation_request " 
                "user_id=%s latency_ms=%.2f fallback=%s",
                user_id, latency_ms, "False"
    )

    record_request(
        latency_ms=latency_ms,
        fallback=False,
    )

    return {
        "user_id": user_id,
        "recommendations": (
            recommendations[["product_id", "score"]]
            .to_dict(orient="records")),
        "fallback": False,
    }

@app.get("/metrics")
def metrics():
    return get_metrics()