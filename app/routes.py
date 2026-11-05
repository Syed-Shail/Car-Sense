from flask import Blueprint, request, jsonify
from .services.hybrid_recommender import SORT_OPTIONS, hybrid_recommend_with_suggestion
from .services.llm_query_understanding import understand_query
from .services.reference_resolver import resolve_reference, cars
api = Blueprint("api", __name__)


@api.route("/recommend", methods=["POST"])
def recommend():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400
    query = data.get("query", "")
    if not isinstance(query, str) or not query.strip():
        return jsonify({"error": "A non-empty string 'query' is required."}), 400
    if len(query) > 600:
        return jsonify({"error": "Query must be 600 characters or fewer."}), 400
    parsed = understand_query(query, cars)
    parsed = resolve_reference(parsed)
    sort_by = data.get("sort_by")
    if sort_by is None:
        sort_by = "budget_fit" if parsed.get("budget") is not None else "recommended"
    if not isinstance(sort_by, str) or sort_by not in SORT_OPTIONS:
        sort_by = "budget_fit" if parsed.get("budget") is not None else "recommended"
    if sort_by == "budget_fit" and parsed.get("budget") is None:
        sort_by = "recommended"

    reference = next((
        car for car in cars
        if parsed.get("reference_model")
        and car.get("model", "").lower() == parsed["reference_model"].lower()
    ), None)
    comparison = parsed.get("comparison") or {}
    reference_score = None
    reference_seats = None
    if reference:
        score_name = {"performance": "performance_score", "efficiency": "efficiency_score", "offroad": "offroad_score"}.get(comparison.get("type"))
        if score_name:
            reference_score = reference.get("ai", {}).get(score_name)
        reference_seats = reference.get("seating_capacity")

    results, special_suggestion = hybrid_recommend_with_suggestion(
        query=query,
        budget=parsed.get("budget"),
        seats=parsed.get("seats"),
        body_type=parsed.get("body_type"),
        priority=(parsed.get("intent") or ["family"])[0],
        sort_by=sort_by,
        reference_model=parsed.get("reference_model"),
        max_price=parsed.get("max_price"),
        min_price=parsed.get("min_price"),
        vehicle_category=parsed.get("vehicle_category"),
        fuel_type=parsed.get("fuel_type"),
        transmission=parsed.get("transmission"),
        drive_type=parsed.get("drive_type"),
        comparison=comparison,
        reference_score=reference_score,
        reference_seats=reference_seats,
        **{key: parsed.get(key) for key in (
            "turbo_required", "min_bhp", "min_ncap", "min_airbags",
            "adas_required", "sunroof_required", "ventilated_seats_required",
            "camera_360_required", "ev_required", "min_range", "min_mileage",
            "min_boot_space", "min_ground_clearance",
        )}
    )

    return jsonify({
        "parsed_query": parsed,
        "recommendations": results,
        "special_suggestion": special_suggestion,
        "sorted_by": sort_by,
    })
