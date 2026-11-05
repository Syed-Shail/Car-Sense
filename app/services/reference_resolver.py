from .catalog_store import load_catalog


cars = load_catalog()


def find_reference_car(reference_model):

    if not reference_model:
        return None

    reference_model = reference_model.lower()

    for car in cars:

        model = car.get("model", "").lower()

        if reference_model == model:
            return car

    return None


def _starting_price(reference_car):
    prices = [
        variant.get("pricing", {}).get("ex_showroom")
        for variant in reference_car.get("variants", [])
        if isinstance(variant, dict)
        and isinstance(variant.get("pricing"), dict)
        and isinstance(variant["pricing"].get("ex_showroom"), (int, float))
        and variant["pricing"]["ex_showroom"] > 0
    ]
    return min(prices) if prices else None


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

    # Resolve every explicit price comparison independently. For several upper
    # bounds keep the lowest; for lower bounds keep the highest.
    for price_comparison in parsed.get("price_comparisons", []):
        if not isinstance(price_comparison, dict) or price_comparison.get("type") != "price":
            continue
        compared_car = find_reference_car(price_comparison.get("reference_model"))
        reference_price = _starting_price(compared_car) if compared_car else None
        if reference_price is None:
            continue
        if price_comparison.get("operator") == "less_than":
            current = parsed.get("max_price")
            parsed["max_price"] = min(current, reference_price) if current is not None else reference_price
        elif price_comparison.get("operator") == "greater_than":
            current = parsed.get("min_price")
            parsed["min_price"] = max(current, reference_price) if current is not None else reference_price

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

    reference_price = _starting_price(reference_car)

    if comparison_type == "price" and reference_price is not None:

        if operator == "less_than":
            current = parsed.get("max_price")
            parsed["max_price"] = min(current, reference_price) if current is not None else reference_price

        elif operator == "greater_than":
            current = parsed.get("min_price")
            parsed["min_price"] = max(current, reference_price) if current is not None else reference_price

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
