"""Optional LLM extraction with a deterministic offline fallback.

The catalog remains the source of truth: the LLM only returns structured
preferences, and reference models are resolved against the local catalog.
"""
import json
import os

from .query_parser import parse_query


def understand_query(query, cars):
    parsed = parse_query(query, cars)
    if not os.getenv("OPENAI_API_KEY"):
        parsed["query_understanding"] = "rules"
        return parsed

    try:
        from openai import OpenAI

        response = OpenAI().responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            instructions=(
                "Extract vehicle shopping preferences from the user's text. "
                "Return only a JSON object with keys budget (integer INR or null), "
                "seats (integer or null), body_type, fuel_type, transmission, "
                "drive_type, intent (array from family/performance/city/luxury/"
                "offroad/safety/efficiency), vehicle_category (sports_car or null), "
                "reference_model, and comparison "
                "(object with type and operator). Never infer a preference not stated."
            ),
            input=query,
        )
        extracted = json.loads(response.output_text)
        expected_types = {
            "budget": int, "seats": int, "body_type": str, "fuel_type": str,
            "transmission": str, "drive_type": str, "reference_model": str,
            "intent": list, "comparison": dict, "vehicle_category": str,
        }
        for key, expected in expected_types.items():
            value = extracted.get(key)
            if isinstance(value, expected) and not isinstance(value, bool):
                existing = parsed.get(key)
                if key == "comparison":
                    if isinstance(existing, dict) and existing.get("type"):
                        continue
                elif existing not in (None, "", [], {}):
                    # Keep explicit rule-based values authoritative; the LLM
                    # may fill gaps but must not weaken a parsed hard limit.
                    continue
                if key == "budget" and value <= 0:
                    continue
                if key == "seats" and not 1 <= value <= 20:
                    continue
                if key == "body_type":
                    catalog_types = {car.get("body_type", "").lower(): car.get("body_type") for car in cars}
                    value = catalog_types.get(value.strip().lower())
                    if value is None:
                        continue
                if key == "fuel_type":
                    fuel_names = {
                        "petrol": "Petrol", "diesel": "Diesel", "electric": "Electric",
                        "cng": "CNG", "hybrid": "Hybrid",
                    }
                    if value.strip().lower() not in fuel_names:
                        continue
                    value = fuel_names[value.strip().lower()]
                if key == "transmission":
                    normalized = value.strip().lower()
                    if normalized not in {"manual", "automatic"}:
                        continue
                    value = normalized.title()
                if key == "reference_model":
                    models = {car.get("model", "").lower(): car.get("model") for car in cars}
                    value = models.get(value.strip().lower())
                    if value is None:
                        continue
                if key == "comparison":
                    comparison_type = value.get("type")
                    operator = value.get("operator")
                    if comparison_type not in {"price", "performance", "efficiency", "offroad", "seating"} or operator not in {"less_than", "greater_than"}:
                        continue
                if key == "vehicle_category" and value != "sports_car":
                    continue
                if key == "intent":
                    value = [item for item in value if item in {
                        "family", "performance", "city", "luxury", "offroad", "safety", "efficiency"
                    } and isinstance(item, str)]
                parsed[key] = value
        # Boolean and numeric hard constraints are safer from explicit rules.
        parsed["query_understanding"] = "llm+rules"
    except Exception:
        # Keep recommendations available if the provider, key, network, or
        # response format is unavailable.
        parsed["query_understanding"] = "rules_fallback"
    return parsed
