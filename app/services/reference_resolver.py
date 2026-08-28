import json


DATA_FILE = "/Users/shail/Desktop/Car Projecr/data/processed/enhanced_vehicles.json"


with open(DATA_FILE, "r", encoding="utf-8") as file:
    cars = json.load(file)


def find_reference_car(reference_model):

    if not reference_model:
        return None

    reference_model = reference_model.lower()

    for car in cars:

        model = car.get("model", "").lower()

        if reference_model in model:
            return car

    return None


def resolve_reference(parsed):

    reference_model = parsed.get("reference_model")

    if not reference_model:
        return parsed

    reference_car = find_reference_car(reference_model)

    if not reference_car:
        return parsed

    # --------------------------------
    # Inherit missing attributes
    # --------------------------------

    if parsed.get("body_type") is None:
        parsed["body_type"] = reference_car.get("body_type")

    if parsed.get("fuel_type") is None:
        parsed["fuel_type"] = reference_car.get("fuel_type")

    if parsed.get("seats") is None:
        parsed["seats"] = reference_car.get(
            "seating_capacity"
        )

    # --------------------------------
    # Comparison
    # --------------------------------

    comparison = parsed.get("comparison")

    if not comparison:
        return parsed

    comparison_type = comparison.get("type")
    operator = comparison.get("operator")

    # --------------------------------
    # Price comparison
    # --------------------------------

    reference_price = min(
    variant["pricing"]["ex_showroom"]
    for variant in reference_car["variants"]
    )

    if comparison_type == "price" and reference_price:

        if operator == "less_than":
            parsed["max_price"] = reference_price

        elif operator == "greater_than":
            parsed["min_price"] = reference_price

    # --------------------------------
    # Other comparisons
    # --------------------------------

    if comparison_type == "performance":

        reference_score = (
            reference_car
            .get("ai", {})
            .get("performance_score")
        )

        if reference_score is not None:
            parsed["min_performance"] = reference_score

    elif comparison_type == "efficiency":

        reference_score = (
            reference_car
            .get("ai", {})
            .get("efficiency_score")
        )

        if reference_score is not None:
            parsed["min_efficiency"] = reference_score

    elif comparison_type == "offroad":

        reference_score = (
            reference_car
            .get("ai", {})
            .get("offroad_score")
        )

        if reference_score is not None:
            parsed["min_offroad"] = reference_score

    elif comparison_type == "seating":

        reference_seats = reference_car.get(
            "seating_capacity"
        )

        if reference_seats is not None:
            parsed["min_seats"] = reference_seats

    return parsed