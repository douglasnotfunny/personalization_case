import time


requests_total = 0
fallback_total = 0
errors_total = 0
latency_total = 0.0


def record_request(latency_ms: float, fallback: bool):
    global requests_total, fallback_total, latency_total

    requests_total += 1
    latency_total += latency_ms

    if fallback:
        fallback_total += 1


def record_error():
    global errors_total

    errors_total += 1


def get_metrics() -> dict:
    average_latency = (
        latency_total / requests_total
        if requests_total > 0
        else 0
    )

    return {
        "requests_total": requests_total,
        "fallback_total": fallback_total,
        "errors_total": errors_total,
        "average_latency_ms": round(average_latency, 2),
    }