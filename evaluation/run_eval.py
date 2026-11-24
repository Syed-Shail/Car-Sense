"""Evaluate CarSense query understanding and end-to-end recommendations.

Hand-labelled natural-language queries are checked in two ways. evaluation/queries.json (58
queries) was used while improving the parser; evaluation/heldout.json (30 queries) was written
separately and never used for tuning, so it gives the honest estimate.

1. Query understanding: every structured field the parser produces is compared with the
   label. Unlabelled fields are expected to stay empty, so false positives count as errors.
2. Recommendations: each query is sent to POST /recommend and every returned car in the
   primary shortlist is checked against the user's stated constraints (budget, minimum
   price, seats, body type, fuel and transmission).

Run from the repository root:  python -m evaluation.run_eval
Results are written to evaluation/results.json.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import statistics
import time
import warnings

warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)

from app.app import app  # noqa: E402
from app.services.hybrid_recommender import AUTOMATIC_TRANSMISSIONS  # noqa: E402
from app.services.query_parser import parse_query  # noqa: E402
from app.services.reference_resolver import cars  # noqa: E402

HERE = Path(__file__).resolve().parent
DEFAULTS = {
    "budget": None, "min_price": None, "seats": None, "body_type": None, "fuel_type": None,
    "transmission": None, "drive_type": None, "reference_model": None, "comparison": None,
    "min_range": None, "min_airbags": None, "min_ncap": None, "sunroof_required": False,
    "camera_360_required": False, "adas_required": False, "turbo_required": False,
}


def predicted_fields(parsed: dict) -> dict:
    out = {field: parsed.get(field, default) or default for field, default in DEFAULTS.items()}
    comparison = parsed.get("comparison") or {}
    out["comparison"] = [comparison["type"], comparison["operator"]] if comparison.get("type") else None
    return out


def satisfies(car: dict, label: dict) -> list[str]:
    """Return the constraints this recommended car breaks."""
    broken = []
    price = car.get("price")
    if label.get("budget") and price and price > label["budget"]:
        broken.append("budget")
    if label.get("min_price") and price and price < label["min_price"]:
        broken.append("min_price")
    if label.get("seats") and (car.get("seats") or 0) < label["seats"]:
        broken.append("seats")
    for field in ("body_type", "fuel_type"):
        if label.get(field) and str(car.get(field, "")).lower() != label[field].lower():
            broken.append(field)
    if label.get("transmission"):
        gearbox = str(car.get("transmission", "")).lower()
        family = "automatic" if gearbox in AUTOMATIC_TRANSMISSIONS else "manual"
        if family != label["transmission"].lower():
            broken.append("transmission")
    return broken


def evaluate(queries: list[dict], client) -> dict:

    # 1. Query understanding
    field_total = field_correct = tp = fp = fn = exact = 0
    per_field: dict[str, list[int]] = {field: [0, 0] for field in DEFAULTS}
    errors = []
    for item in queries:
        label = {field: item.get(field, default) for field, default in DEFAULTS.items()}
        pred = predicted_fields(parse_query(item["q"], cars))
        query_ok = True
        for field in DEFAULTS:
            expected, got = label[field], pred[field]
            ok = expected == got
            field_total += 1
            field_correct += ok
            per_field[field][0] += ok
            per_field[field][1] += 1
            if got not in (None, False) and ok:
                tp += 1
            if got not in (None, False) and not ok:
                fp += 1
            if expected not in (None, False) and not ok:
                fn += 1
            if not ok:
                query_ok = False
                errors.append({"query": item["q"], "field": field, "expected": expected, "got": got})
        exact += query_ok
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0

    # 2. End-to-end recommendations through the API
    latencies, cars_checked, cars_ok, queries_all_ok, empty = [], 0, 0, 0, 0
    violations: dict[str, int] = {}
    for item in queries:
        t0 = time.perf_counter()
        response = client.post("/recommend", json={"query": item["q"]})
        latencies.append(time.perf_counter() - t0)
        recs = response.get_json().get("recommendations", [])
        empty += not recs
        all_ok = True
        for car in recs:
            broken = satisfies(car, item)
            cars_checked += 1
            cars_ok += not broken
            all_ok &= not broken
            for name in broken:
                violations[name] = violations.get(name, 0) + 1
        queries_all_ok += all_ok and bool(recs)
    latencies.sort()

    return {
        "queries": len(queries),
        "query_understanding": {
            "field_accuracy": round(field_correct / field_total, 4),
            "constraint_precision": round(precision, 4),
            "constraint_recall": round(recall, 4),
            "constraint_f1": round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0,
            "queries_fully_understood": round(exact / len(queries), 4),
            "per_field_accuracy": {f: round(c / t, 4) for f, (c, t) in per_field.items()},
        },
        "recommendations": {
            "cars_returned": cars_checked,
            "cars_meeting_every_stated_constraint": round(cars_ok / cars_checked, 4) if cars_checked else 0.0,
            "queries_with_all_results_valid": round(queries_all_ok / len(queries), 4),
            "queries_with_no_results": empty,
            "violations_by_constraint": violations,
            "median_latency_ms": round(statistics.median(latencies) * 1000, 1),
            "p95_latency_ms": round(latencies[min(len(latencies) - 1, round(0.95 * (len(latencies) - 1)))] * 1000, 1),
        },
        "errors": errors,
    }


def main() -> None:
    client = app.test_client()
    client.post("/recommend", json={"query": "warm up"})  # load the embedding model before timing
    report = {
        # Used while developing the parser fixes.
        "development": evaluate(json.loads((HERE / "queries.json").read_text()), client),
        # Written separately and never used for tuning: the honest estimate.
        "held_out": evaluate(json.loads((HERE / "heldout.json").read_text()), client),
    }
    (HERE / "results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    for name, part in report.items():
        print(f"== {name}")
        print(json.dumps({k: v for k, v in part.items() if k != "errors"}, indent=2))
        print(f"{len(part['errors'])} field errors (see evaluation/results.json)")


if __name__ == "__main__":
    main()
