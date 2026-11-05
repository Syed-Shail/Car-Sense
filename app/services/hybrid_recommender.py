from pathlib import Path
import faiss
import joblib
import numpy as np
import pandas as pd
import logging
import re
from sentence_transformers import SentenceTransformer
from .catalog_store import load_catalog


ROOT = Path(__file__).resolve().parents[2]
INDEX_FILE = ROOT / "data/processed/car_index.faiss"
MODEL_FILE = ROOT / "data/processed/ranker.pkl"


logger = logging.getLogger(__name__)
print("Loading model...")
try:
    embedding_model = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
    print("Embedding model loaded")
except Exception as exc:
    embedding_model = None
    logger.warning("Embedding model unavailable; using offline catalog text retrieval: %s", exc)


cars = load_catalog()

index = faiss.read_index(str(INDEX_FILE))

saved = joblib.load(MODEL_FILE)

ranker = saved["model"]
body_encoder = saved["body_encoder"]
priority_encoder = saved["priority_encoder"]


def semantic_candidates(query, top_k=50):
    if not query or not query.strip():
        return cars
    if embedding_model is None:
        query_terms = set(re.findall(r"[a-z0-9]+", query.lower()))
        scored = []
        for car in cars:
            text = " ".join([
                str(car.get("brand", "")), str(car.get("model", "")),
                str(car.get("body_type", "")), str(car.get("segment", "")),
                str(car.get("base_specs", {}).get("fuel_type", "")),
                str(car.get("base_specs", {}).get("drive", "")),
            ]).lower()
            terms = set(re.findall(r"[a-z0-9]+", text))
            scored.append((len(query_terms & terms), car))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        matches = [car for score, car in scored[:top_k] if score]
        return matches or cars
    query_vector = embedding_model.encode([query])
    top_k = min(top_k, len(cars))
    distances, indices = index.search(
        np.array(query_vector),
        top_k
    )

    return [cars[i] for i in indices[0] if 0 <= i < len(cars)]


def _variants(car):
    variants = car.get("variants", []) if isinstance(car, dict) else []
    return variants if isinstance(variants, list) else []


def _number(value, default=0):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else default


def _variant_number(variant, section, key):
    values = variant.get(section) if isinstance(variant, dict) else None
    return _number(values.get(key)) if isinstance(values, dict) else 0


def _best_variant(car, constraints):
    """Return the least expensive variant that satisfies variant constraints."""
    matches = []
    for variant in _variants(car):
        if not isinstance(variant, dict):
            continue
        pricing = variant.get("pricing")
        pricing = pricing if isinstance(pricing, dict) else {}
        price = _number(pricing.get("ex_showroom"), None)
        if price is None or price <= 0:
            continue
        engine = variant.get("engine")
        safety = variant.get("safety")
        efficiency = variant.get("efficiency")
        features = variant.get("features")
        ev = variant.get("ev")
        engine = engine if isinstance(engine, dict) else {}
        safety = safety if isinstance(safety, dict) else {}
        efficiency = efficiency if isinstance(efficiency, dict) else {}
        features = features if isinstance(features, dict) else {}
        ev = ev if isinstance(ev, dict) else {}
        base_specs = car.get("base_specs") if isinstance(car.get("base_specs"), dict) else {}
        requested_transmission = constraints.get("transmission")
        actual_transmission = str(engine.get("transmission", "")).lower()
        if requested_transmission:
            if requested_transmission.lower() == "automatic":
                if actual_transmission not in {"automatic", "amt", "cvt", "dct", "at", "imt"}:
                    continue
            elif requested_transmission.lower() == "manual":
                if actual_transmission != "manual":
                    continue
        if constraints.get("turbo_required") and not engine.get("turbo", base_specs.get("turbo")):
            continue
        if constraints.get("fuel_type"):
            wanted = constraints["fuel_type"].lower()
            actual = str(engine.get("fuel_type", base_specs.get("fuel_type", ""))).lower()
            if wanted not in actual:
                continue
        if constraints.get("drive_type"):
            actual_drive = engine.get("drive", base_specs.get("drive", ""))
            if str(actual_drive).lower() != constraints["drive_type"].lower():
                continue
        if constraints.get("min_bhp") and _number(engine.get("bhp")) < constraints["min_bhp"]:
            continue
        if constraints.get("min_ncap") and _number(safety.get("ncap")) < constraints["min_ncap"]:
            continue
        if constraints.get("min_airbags") and _number(safety.get("airbags")) < constraints["min_airbags"]:
            continue
        if constraints.get("adas_required") and not safety.get("adas_level_2"):
            continue
        if constraints.get("sunroof_required") and not features.get("sunroof"):
            continue
        if constraints.get("ventilated_seats_required") and not features.get("ventilated_seats"):
            continue
        if constraints.get("camera_360_required") and not features.get("camera_360"):
            continue
        if constraints.get("ev_required") and not ev.get("is_ev"):
            continue
        if constraints.get("min_range") and _number(ev.get("range_km")) < constraints["min_range"]:
            continue
        if constraints.get("min_mileage") and _number(efficiency.get("arai")) < constraints["min_mileage"]:
            continue
        matches.append((price, variant))
    if not matches:
        return None, None, {}
    price, variant = min(matches, key=lambda item: item[0])
    metrics = {
        "arai_mileage": _variant_number(variant, "efficiency", "arai"),
        "ev_range_km": _variant_number(variant, "ev", "range_km"),
        "warranty_years": _variant_number(variant, "warranty", "years"),
        "resale_quality": {"poor": 1, "average": 2, "good": 3, "strong": 4, "excellent": 5}.get(
            str((variant.get("pricing") if isinstance(variant.get("pricing"), dict) else {}).get("resale_value", "")).lower(), 0
        ),
    }
    return price, variant, metrics


def apply_filters(
    candidates,
    budget=None,
    seats=None,
    body_type=None,
    max_price=None,
    min_price=None,
    **constraints
):
    filtered = []

    for car in candidates:

        min_car_price, selected_variant, variant_metrics = _best_variant(car, constraints)
        if selected_variant is None:
            continue

        # -----------------------------
        # Normal budget filter
        # -----------------------------

        if budget is not None:
            if min_car_price > budget:
                continue

        # -----------------------------
        # Comparison: cheaper than X
        # -----------------------------

        if max_price is not None:
            if min_car_price >= max_price:
                continue

        # -----------------------------
        # Comparison: more expensive than X
        # -----------------------------

        if min_price is not None:
            if min_car_price <= min_price:
                continue

        # -----------------------------
        # Seats
        # -----------------------------

        if seats is not None:
            if car.get("seating_capacity", 0) < seats:
                continue

        # -----------------------------
        # Body type
        # -----------------------------

        if body_type is not None:
            if car.get("body_type", "").lower() != body_type.lower():
                continue

        if constraints.get("min_boot_space") and (car.get("dimensions", {}).get("boot_space") or 0) < constraints["min_boot_space"]:
            continue
        if constraints.get("min_ground_clearance") and (car.get("dimensions", {}).get("ground_clearance") or 0) < constraints["min_ground_clearance"]:
            continue

        if constraints.get("vehicle_category") == "sports_car":
            body = str(car.get("body_type", "")).lower()
            segment = str(car.get("segment", "")).lower()
            sports_styles = {"coupe", "convertible", "gran turismo"}
            sports_segments = ("sports car", "sports sedan", "sports roadster", "luxury sports", "roadster")
            if body not in sports_styles and not any(term in segment for term in sports_segments):
                continue

        comparison = constraints.get("comparison") or {}
        score_key = {"performance": "performance_score", "efficiency": "efficiency_score", "offroad": "offroad_score"}.get(comparison.get("type"))
        if comparison.get("operator") == "greater_than" and score_key:
            reference_score = constraints.get("reference_score")
            if reference_score is not None and car.get("ai", {}).get(score_key, 0) <= reference_score:
                continue
        if comparison.get("type") == "seating" and car.get("seating_capacity", 0) <= (constraints.get("reference_seats") or 0):
            continue

        matched_car = dict(car)
        matched_car["_matched_price"] = min_car_price
        matched_car["_matched_variant"] = selected_variant.get("variant_name")
        matched_car["_matched_transmission"] = selected_variant.get("engine", {}).get("transmission")
        matched_car["_matched_fuel_type"] = selected_variant.get("engine", {}).get(
            "fuel_type", car.get("base_specs", {}).get("fuel_type")
        )
        matched_car["_sort_metrics"] = variant_metrics
        filtered.append(matched_car)

    return filtered


def ml_rerank(filtered_cars, budget, seats, priority, limit=5):
    ranked = []
    budget = budget or 5000000
    seats = seats or 5
    priority = priority or "family"

    for car in filtered_cars:
        min_price = car.get("_matched_price") or min(
            variant["pricing"]["ex_showroom"] for variant in car["variants"]
        )

        features = pd.DataFrame([{
            "budget": budget,
            "seats": seats,
            "body_type": body_encoder.transform([car["body_type"]])[0],
            "priority": priority_encoder.transform([priority])[0],
            "car_price": min_price,
            "family_score": car["ai"]["family_score"],
            "performance_score": car["ai"]["performance_score"],
            "city_score": car["ai"]["city_score"],
            "luxury_score": car["ai"]["luxury_score"],
            "offroad_score": car["ai"]["offroad_score"],
            "safety_score": car["ai"]["safety_score"],
            "efficiency_score": car["ai"]["efficiency_score"]
        }])

        probability = ranker.predict_proba(features)[0][1]

        ranked.append({
            "brand": car["brand"],
            "model": car["model"],
            "score": probability,
            "price": min_price,
            "variant": car.get("_matched_variant"),
            "body_type": car.get("body_type"),
            "seats": car.get("seating_capacity"),
            "fuel_type": car.get("_matched_fuel_type") or car.get("base_specs", {}).get("fuel_type"),
            "transmission": car.get("_matched_transmission") or car.get("base_specs", {}).get("transmission"),
            "arai_mileage": car.get("_sort_metrics", {}).get("arai_mileage", 0),
            "ev_range_km": car.get("_sort_metrics", {}).get("ev_range_km", 0),
            "warranty_years": car.get("_sort_metrics", {}).get("warranty_years", 0),
            "resale_quality": car.get("_sort_metrics", {}).get("resale_quality", 0),
            "safety_score": car.get("ai", {}).get("safety_score", 0),
            "performance_score": car.get("ai", {}).get("performance_score", 0),
            "efficiency_score": car.get("ai", {}).get("efficiency_score", 0),
            "luxury_score": car.get("ai", {}).get("luxury_score", 0),
            "city_score": car.get("ai", {}).get("city_score", 0),
            "offroad_score": car.get("ai", {}).get("offroad_score", 0),
            "boot_space": car.get("dimensions", {}).get("boot_space", 0),
            "ground_clearance": car.get("dimensions", {}).get("ground_clearance", 0),
        })

    ranked.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return ranked[:limit] if limit is not None else ranked


def _capability_profile(car):
    """Build a comparable model profile from the cheapest catalog variant."""
    variants = _variants(car)
    valid_variants = [
        variant for variant in variants
        if isinstance(variant, dict)
        and isinstance(variant.get("pricing"), dict)
        and isinstance(variant["pricing"].get("ex_showroom"), (int, float))
        and variant["pricing"]["ex_showroom"] > 0
    ]
    variant = min(valid_variants, key=lambda item: item["pricing"]["ex_showroom"]) if valid_variants else {}
    engine = variant.get("engine") if isinstance(variant.get("engine"), dict) else {}
    safety = variant.get("safety") if isinstance(variant.get("safety"), dict) else {}
    efficiency = variant.get("efficiency") if isinstance(variant.get("efficiency"), dict) else {}
    base = car.get("base_specs") if isinstance(car.get("base_specs"), dict) else {}
    dimensions = car.get("dimensions") if isinstance(car.get("dimensions"), dict) else {}
    ai = car.get("ai") if isinstance(car.get("ai"), dict) else {}
    profile = {
        "seats": car.get("seating_capacity"),
        "bhp": engine.get("bhp"),
        "torque": engine.get("torque"),
        "ncap": safety.get("ncap"),
        "airbags": safety.get("airbags"),
        "ground_clearance": dimensions.get("ground_clearance"),
        "boot_space": dimensions.get("boot_space"),
        "mileage": efficiency.get("arai"),
        "drive": engine.get("drive", base.get("drive")),
        "fuel": engine.get("fuel_type", base.get("fuel_type")),
    }
    profile.update({
        key: ai.get(key)
        for key in (
            "family_score", "performance_score", "city_score", "luxury_score",
            "offroad_score", "safety_score", "efficiency_score",
        )
    })
    return profile


_CAPABILITY_WEIGHTS = {
    "family_score": (0.08, 10), "performance_score": (0.08, 10),
    "city_score": (0.05, 10), "luxury_score": (0.05, 10),
    "offroad_score": (0.10, 10), "safety_score": (0.08, 10),
    "efficiency_score": (0.07, 10), "seats": (0.08, 7),
    "bhp": (0.12, 500), "torque": (0.06, 1000),
    "ncap": (0.08, 5), "airbags": (0.04, 10),
    "ground_clearance": (0.08, 350), "boot_space": (0.05, 1000),
    "mileage": (0.04, 40), "drive": (0.07, None), "fuel": (0.03, None),
}


def _capability_similarity(car, reference):
    """Return 0-100 similarity across catalog fields present for both cars."""
    candidate = _capability_profile(car)
    target = _capability_profile(reference)
    weighted_score = total_weight = 0.0
    for field, (weight, scale) in _CAPABILITY_WEIGHTS.items():
        left, right = candidate.get(field), target.get(field)
        if left is None or right is None:
            continue
        if scale is None:
            similarity = 1.0 if str(left).strip().lower() == str(right).strip().lower() else 0.0
        else:
            try:
                similarity = max(0.0, 1.0 - abs(float(left) - float(right)) / scale)
            except (TypeError, ValueError):
                continue
        weighted_score += weight * similarity
        total_weight += weight
    return round(100 * weighted_score / total_weight) if total_weight else None


def _budget_flexible_score(car, priority, requested_seats=None):
    """Score the preference dimensions while leaving vehicle price out."""
    scores = car.get("ai", {})
    profiles = {
        "family": {"family_score": 0.35, "safety_score": 0.30},
        "performance": {"performance_score": 0.60, "safety_score": 0.20},
        "city": {"city_score": 0.50, "efficiency_score": 0.30},
        "luxury": {"luxury_score": 0.60, "performance_score": 0.20, "safety_score": 0.20},
        "offroad": {"offroad_score": 0.50, "performance_score": 0.30, "safety_score": 0.20},
        "safety": {"safety_score": 0.70, "family_score": 0.20},
        "efficiency": {"efficiency_score": 0.60, "city_score": 0.30},
    }
    weights = profiles.get(priority, profiles["family"])
    weighted = sum(scores.get(name, 0) * weight for name, weight in weights.items())
    total_weight = sum(weights.values())
    if priority == "family" and requested_seats:
        seat_fit = 10 if car.get("seating_capacity", 0) >= requested_seats else 0
        weighted += 0.20 * seat_fit
        total_weight += 0.20
    return weighted / total_weight if total_weight else 0


def _as_suggestion(car, priority, budget, seats):
    price = car["_matched_price"]
    budget_difference = price - budget
    relation = "above" if budget_difference > 0 else "at" if budget_difference == 0 else "below"
    return {
        "brand": car["brand"],
        "model": car["model"],
        "price": price,
        "variant": car.get("_matched_variant"),
        "body_type": car.get("body_type"),
        "seats": car.get("seating_capacity"),
        "fuel_type": car.get("_matched_fuel_type") or car.get("base_specs", {}).get("fuel_type"),
        "score": min(1.0, max(0.0, _budget_flexible_score(car, priority, seats) / 10)),
        "budget_relation": relation,
        "budget_difference": budget_difference,
    }


SORT_OPTIONS = {
    "recommended", "budget_fit", "price_low", "price_high", "seats",
    "fuel_type", "transmission", "body_type", "mileage", "safety",
    "performance", "comfort", "city", "offroad", "boot_space",
    "ground_clearance", "ev_range", "warranty", "resale",
}


def _intent_fit_score(car, priority):
    """Order matches by the requested driving priority using catalog scores."""
    profiles = {
        "family": {"family_score": 0.35, "safety_score": 0.30},
        "performance": {"performance_score": 0.60, "safety_score": 0.20},
        "city": {"city_score": 0.50, "efficiency_score": 0.30},
        "luxury": {"luxury_score": 0.60, "performance_score": 0.20, "safety_score": 0.20},
        "offroad": {"offroad_score": 0.50, "performance_score": 0.30, "safety_score": 0.20},
        "safety": {"safety_score": 0.70, "family_score": 0.20},
        "efficiency": {"efficiency_score": 0.60, "city_score": 0.30},
    }
    weights = profiles.get(priority, profiles["family"])
    return sum(car.get(field, 0) * weight for field, weight in weights.items())


def _sort_recommendations(results, sort_by, budget=None, preferred_fuel=None, priority=None):
    if sort_by not in SORT_OPTIONS:
        sort_by = "recommended"
    if sort_by == "recommended":
        if priority == "offroad":
            key = lambda car: (
                -_intent_fit_score(car, priority),
                -car.get("ground_clearance", 0),
                -car["score"],
            )
        else:
            key = lambda car: (-_intent_fit_score(car, priority or "family"), -car["score"])
    elif sort_by == "budget_fit":
        key = (lambda car: (abs(budget - car["price"]), -car["score"])) if budget is not None else (lambda car: -car["score"])
    elif sort_by == "price_low":
        key = lambda car: (car["price"], -car["score"])
    elif sort_by == "price_high":
        key = lambda car: (-car["price"], -car["score"])
    elif sort_by == "seats":
        key = lambda car: (-car.get("seats", 0), -car["score"])
    elif sort_by == "fuel_type":
        wanted = (preferred_fuel or "").lower()
        key = lambda car: (0 if wanted and wanted in str(car.get("fuel_type", "")).lower() else 1, str(car.get("fuel_type") or "").lower(), -car["score"])
    elif sort_by == "transmission":
        key = lambda car: (str(car.get("transmission") or "").lower(), -car["score"])
    elif sort_by == "body_type":
        key = lambda car: (str(car.get("body_type") or "").lower(), -car["score"])
    else:
        metric = {
            "mileage": "arai_mileage", "safety": "safety_score",
            "performance": "performance_score", "comfort": "luxury_score",
            "city": "city_score", "offroad": "offroad_score",
            "boot_space": "boot_space", "ground_clearance": "ground_clearance",
            "ev_range": "ev_range_km", "warranty": "warranty_years",
            "resale": "resale_quality",
        }[sort_by]
        key = lambda car: (-car.get(metric, 0), -car["score"])
    return sorted(results, key=key)


def hybrid_recommend_with_suggestion(
    query,
    budget=None,
    seats=None,
    body_type=None,
    priority=None,
    max_price=None,
    min_price=None,
    sort_by="recommended",
    reference_model=None,
    **constraints
):
    print("Semantic retrieval...")
    candidates = semantic_candidates(
        query,
        # Comparative queries must search the full catalog: a vehicle can be
        # a strong alternative even when its model name is not semantically
        # close to the wording of the request.
        top_k=len(cars) if (
            budget is not None
            or sort_by != "recommended"
            or constraints.get("vehicle_category")
            or constraints.get("comparison")
            or max_price is not None
            or min_price is not None
        ) else 50,
    )

    print("Applying filters...")
    filtered = apply_filters(
        candidates,
        budget=budget,
        seats=seats,
        body_type=body_type,
        max_price=max_price,
        min_price=min_price,
        **constraints,
    )

    # Semantic retrieval is a candidate generator. If its top-k misses every
    # valid vehicle, apply the same hard constraints to the full catalog.
    if not filtered:
        filtered = apply_filters(
            cars, budget=budget, seats=seats, body_type=body_type,
            max_price=max_price, min_price=min_price, **constraints
        )

    print("ML reranking...")
    ranked = ml_rerank(
        filtered,
        budget,
        seats,
        priority or "family",
        limit=None,
    )

    special_suggestion = None
    ranked = _sort_recommendations(
        ranked, sort_by, budget=budget, preferred_fuel=constraints.get("fuel_type"),
        priority=priority or "family",
    )
    comparison = constraints.get("comparison") or {}
    if reference_model and comparison.get("type") == "price" and comparison.get("operator") == "less_than":
        reference = next((
            car for car in cars
            if str(car.get("model", "")).strip().lower() == reference_model.strip().lower()
        ), None)
        if reference:
            for item in ranked:
                source = next((
                    car for car in filtered
                    if car.get("brand") == item.get("brand") and car.get("model") == item.get("model")
                ), None)
                item["capability_match"] = _capability_similarity(source, reference) if source else None
                item["compared_with"] = reference_model
            # Similarity is the default ordering for a cheaper-alternative request.
            # Explicit user-selected sort choices remain in control.
            if sort_by == "recommended":
                ranked.sort(key=lambda item: (
                    -(item.get("capability_match") if item.get("capability_match") is not None else -1),
                    -item.get("score", 0),
                ))
    if budget is not None:
        for item in ranked:
            item["budget_difference"] = budget - item["price"]
        flexible = apply_filters(
            candidates,
            budget=None,
            seats=seats,
            body_type=body_type,
            max_price=max_price,
            min_price=min_price,
            **constraints,
        )
        regular_keys = {(item["brand"], item["model"]) for item in ranked}
        alternatives = [
            car for car in flexible
            if (car["brand"], car["model"]) not in regular_keys
        ]
        if alternatives:
            special_car = max(
                alternatives,
                key=lambda car: _budget_flexible_score(car, priority or "family", seats),
            )
            special_suggestion = _as_suggestion(
                special_car, priority or "family", budget, seats
            )

    ranked = ranked[:5]
    return ranked, special_suggestion


def hybrid_recommend(*args, **kwargs):
    """Backward-compatible list-only recommendation entry point."""
    recommendations, _ = hybrid_recommend_with_suggestion(*args, **kwargs)
    return recommendations


if __name__ == "__main__":
    results = hybrid_recommend(
        query="Need a rugged family SUV for long trips",
        budget=10000000,
        seats=5,
        body_type="SUV",
        priority="luxury"
    )

    for car in results:
        print(car)
