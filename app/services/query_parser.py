import re


# ---------------------------------------------------------
# DOMAIN VOCABULARY
# ---------------------------------------------------------

BODY_TYPES = {
    "SUV": [
        "suv",
        "sports utility",
        "sport utility"
    ],

    "Sedan": [
        "sedan"
    ],

    "Hatchback": [
        "hatchback",
        "hatch"
    ],

    "MPV": [
        "mpv",
        "muv",
        "minivan"
    ],

    "Coupe": [
        "coupe"
    ],

    "Convertible": [
        "convertible"
    ]
}


FUEL_TYPES = {
    "Petrol": [
        "petrol",
        "gasoline"
    ],

    "Diesel": [
        "diesel"
    ],

    "Electric": [
        "electric",
        "electric vehicle",
        "ev"
    ],

    "CNG": [
        "cng"
    ],

    "Hybrid": [
        "hybrid"
    ]
}


TRANSMISSIONS = {
    "Automatic": [
        "automatic",
        "auto",
        "amt",
        "dct",
        "cvt"
    ],

    "Manual": [
        "manual",
        "stick shift"
    ]
}


DRIVE_TYPES = {
    "AWD": [
        "awd",
        "all wheel drive",
        "all-wheel drive"
    ],

    "4WD": [
        "4wd",
        "4x4",
        "four wheel drive",
        "four-wheel drive"
    ],

    "FWD": [
        "fwd",
        "front wheel drive",
        "front-wheel drive"
    ],

    "RWD": [
        "rwd",
        "rear wheel drive",
        "rear-wheel drive"
    ]
}


INTENTS = {
    "performance": [
        "sports car",
        "sports cars",
        "sportscar",
        "sportscars",
        "supercar",
        "supercars",
        "roadster",
        "track car",
        "track day",
        "track-ready",
        "spirited driving",
        "sharp handling",
        "fast acceleration",
        "thrilling",
        "weekend drive",
        "sporty",
        "fast",
        "powerful",
        "performance",
        "quick",
        "exciting to drive",
        "high-performance",
    ],

    "family": [
        "family",
        "family car",
        "family vehicle",
        "family trips", "school run", "kid-friendly", "roomy family", "family hauler"
    ],

    "offroad": [
        "offroad",
        "off-road",
        "off roading",
        "offroading",
        "rugged",
        "rough roads",
        "rough road",
        "bad roads",
        "4x4",
        "adventure", "trail driving", "unpaved roads", "camping trips", "ground clearance"
    ],

    "efficiency": [
        "fuel efficient",
        "fuel-efficient",
        "good mileage",
        "high mileage",
        "fuel economy",
        "economical",
        "low running costs", "save on fuel", "saving fuel", "commuter car", "cheap to run"
    ],

    "luxury": [
        "luxury",
        "luxurious",
        "premium",
        "executive", "high-end", "premium cabin", "luxurious interior", "comfort cruiser"
    ],

    "city": [
        "city",
        "city driving",
        "urban",
        "easy to park", "easy parking", "daily commute", "stop-and-go", "city commute"
    ],

    "safety": [
        "safe car", "safest", "safety-focused", "peace of mind", "protect my family"
    ]
}


SPORTS_CAR_TERMS = (
    "sports car", "sports cars", "sportscar", "sportscars", "supercar",
    "supercars", "roadster", "track car", "grand tourer", "gran turismo",
)


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def contains_any(text, terms):
    """
    Returns True for a whole phrase or token, avoiding matches inside
    unrelated words.
    """
    return any(
        re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text)
        for term in terms
    )


# ---------------------------------------------------------
# BUDGET
# ---------------------------------------------------------

def extract_budget(query):
    """
    Handles examples such as:

    20 lakh
    20 lakhs
    20 lac
    20 l
    1.5 crore
    2000000
    """

    # Combined amount, such as "1 crore 50 lakh".
    combined_match = re.search(
        r'(\d+(?:\.\d+)?)\s*(?:crore|crores|cr)\s*(?:and\s*)?(\d+(?:\.\d+)?)\s*(?:lakh|lakhs|lac|l)\b',
        query,
    )
    if combined_match:
        if combined_match.start(1) > 0 and query[combined_match.start(1) - 1] in "-−":
            return None
        crore_value, lakh_value = map(float, combined_match.groups())
        return int(crore_value * 10000000 + lakh_value * 100000)

    # Indian lakh format
    lakh_match = re.search(
        r'(\d+(?:\.\d+)?)\s*(?:lakh|lakhs|lac|l)\b',
        query
    )

    if lakh_match:
        if lakh_match.start(1) > 0 and query[lakh_match.start(1) - 1] in "-−":
            return None
        value = float(lakh_match.group(1))
        return int(value * 100000)

    # Indian crore format
    crore_match = re.search(
        r'(\d+(?:\.\d+)?)\s*(?:crore|crores|cr)\b',
        query
    )

    if crore_match:
        if crore_match.start(1) > 0 and query[crore_match.start(1) - 1] in "-−":
            return None
        value = float(crore_match.group(1))
        return int(value * 10000000)

    # Explicit rupee amounts
    rupee_match = re.search(
        r'(?:₹|rs\.?|inr)\s*(\d[\d,]*)',
        query
    )

    if rupee_match:
        if rupee_match.start() > 0 and query[rupee_match.start() - 1] in "-−":
            return None
        value = rupee_match.group(1).replace(",", "")
        return int(value)

    # Accept plain rupee amounts only with a clear budget phrase and a
    # plausible car-price magnitude.
    plain_amount = re.search(
        r'\b(?:under|below|within|up\s+to|upto|less\s+than|budget(?:\s+of)?|maximum|max\.?)\s+(\d[\d,]*)\b',
        query,
    )
    if plain_amount:
        if plain_amount.start(1) > 0 and query[plain_amount.start(1) - 1] in "-−":
            return None
        value = int(plain_amount.group(1).replace(",", ""))
        return value if value >= 10000 else None

    return None


_UNIT = {"lakh": 100000, "lakhs": 100000, "lac": 100000, "l": 100000,
         "crore": 10000000, "crores": 10000000, "cr": 10000000}
_AMOUNT = r"(?:₹\s*)?(\d+(?:\.\d+)?)\s*(lakhs?|lac|l|crores?|cr)?"          # unit optional
_AMOUNT_WITH_UNIT = r"(?:₹\s*)?(\d+(?:\.\d+)?)\s*(lakhs?|lac|l|crores?|cr)"  # unit required
_PRICE_RANGE = re.compile(r"\b(?:between|from)?\s*" + _AMOUNT + r"\s*(?:and|to|-|–)\s*" + _AMOUNT_WITH_UNIT + r"\b")
_PRICE_MINIMUM = re.compile(
    r"\b(?:above|over|more\s+than|starting\s+(?:from|at)|at\s+least|minimum(?:\s+of)?)\s+"
    + _AMOUNT_WITH_UNIT + r"\b"
)


def extract_price_bounds(query):
    """Return (min_price, max_price, span) for "between 20 and 30 lakh" or "above 50 lakh", else None.

    A range sets both bounds; a lone lower bound ("above 50 lakh") is a minimum, not a budget.
    """
    match = _PRICE_RANGE.search(query)
    if match and (match.group(2) or match.group(4)):
        low_unit = _UNIT[match.group(2) or match.group(4)]
        low = float(match.group(1)) * low_unit
        high = float(match.group(3)) * _UNIT[match.group(4)]
        if 0 < low < high:
            return int(low), int(high), match.span()
    match = _PRICE_MINIMUM.search(query)
    if match:
        return int(float(match.group(1)) * _UNIT[match.group(2)]), None, match.span()
    return None


def extract_numeric_constraint(query, patterns):
    for pattern in patterns:
        match = re.search(pattern, query)
        if match:
            value = match.group(1).replace(",", "")
            return float(value) if "." in value else int(value)
    return None


# ---------------------------------------------------------
# SEATS
# ---------------------------------------------------------

NUMBER_WORDS = {
    "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9,
}
_COUNT = r"(\d+|" + "|".join(NUMBER_WORDS) + r")"


def extract_seats(query):
    """Handles "7 seats", "7-seater", "seven seater", "seats 8", "for 5 people", "family of six"."""
    patterns = [
        _COUNT + r"[\s-]*(?:seaters?|seats?)\b",
        r"\bseats?\s+" + _COUNT + r"\b",
        r"\bfor\s+" + _COUNT + r"\s*(?:people|passengers|persons)\b",
        r"\bfamily\s+of\s+" + _COUNT + r"\b",
        r"\b" + _COUNT + r"\s*(?:people|passengers|persons)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, query)
        if match:
            value = match.group(1)
            return NUMBER_WORDS.get(value) or int(value)

    return None


# ---------------------------------------------------------
# BODY TYPE
# ---------------------------------------------------------

def extract_body_type(query):

    for body_type, terms in BODY_TYPES.items():

        if contains_any(query, terms):
            return body_type

    return None


# ---------------------------------------------------------
# FUEL TYPE
# ---------------------------------------------------------

def extract_fuel_type(query):

    for fuel_type, terms in FUEL_TYPES.items():

        if contains_any(query, terms):
            return fuel_type

    return None


# ---------------------------------------------------------
# TRANSMISSION
# ---------------------------------------------------------

def extract_transmission(query):

    for transmission, terms in TRANSMISSIONS.items():

        if contains_any(query, terms):
            return transmission

    return None


# ---------------------------------------------------------
# DRIVE TYPE
# ---------------------------------------------------------

def extract_drive_type(query):

    for drive_type, terms in DRIVE_TYPES.items():

        if contains_any(query, terms):
            return drive_type

    return None


# ---------------------------------------------------------
# INTENT
# ---------------------------------------------------------

def extract_intents(query):

    intents = []

    for intent, terms in INTENTS.items():

        if contains_any(query, terms):
            intents.append(intent)

    return intents


def extract_vehicle_category(query):
    if contains_any(query, SPORTS_CAR_TERMS):
        return "sports_car"
    return None


# ---------------------------------------------------------
# FEATURES
# ---------------------------------------------------------

def extract_features(query):

    return {

        "turbo_required":
            "turbo" in query or
            "turbocharged" in query,

        "adas_required":
            "adas" in query,

        "sunroof_required":
            "sunroof" in query,

        "ventilated_seats_required":
            "ventilated seats" in query,

        "camera_360_required":
            "360 camera" in query or
            "360-degree camera" in query or
            "360 degree camera" in query,

        "ev_required":
            "electric vehicle" in query or
            "electric" in query or
            re.search(r'\bev\b', query) is not None
    }


# ---------------------------------------------------------
# COMPARISON
# ---------------------------------------------------------

def extract_comparison(query):
    """
    Converts natural language comparisons into
    structured constraints.

    Example:

    "cheaper than Fortuner"

    becomes:

    {
        "type": "price",
        "operator": "less_than"
    }
    """

    comparison = {
        "type": None,
        "operator": None
    }

    # Price
    price_lower = [
        "cheaper",
        "less expensive",
        "lower price",
        "lower priced",
        "lower-priced",
        "budget alternative"
    ]

    price_higher = [
        "more expensive",
        "costlier",
        "higher price",
        "higher priced",
        "higher-priced",
        "premium alternative"
    ]

    # Performance
    performance_higher = [
        "faster",
        "more powerful",
        "better performance"
    ]

    # Efficiency
    efficiency_higher = [
        "better mileage",
        "more efficient",
        "better fuel economy",
        "better fuel efficiency"
    ]

    # Offroad
    offroad_higher = [
        "better offroad",
        "better off-road",
        "better off roading",
        "better offroading",
        "more rugged",
        "better for offroading"
    ]

    # Seating / space
    seating_higher = [
        "more spacious",
        "more seats",
        "bigger"
    ]

    if contains_any(query, price_lower):

        comparison["type"] = "price"
        comparison["operator"] = "less_than"

    elif contains_any(query, price_higher):

        comparison["type"] = "price"
        comparison["operator"] = "greater_than"

    elif contains_any(query, performance_higher):

        comparison["type"] = "performance"
        comparison["operator"] = "greater_than"

    elif contains_any(query, efficiency_higher):

        comparison["type"] = "efficiency"
        comparison["operator"] = "greater_than"

    elif contains_any(query, offroad_higher):

        comparison["type"] = "offroad"
        comparison["operator"] = "greater_than"

    elif contains_any(query, seating_higher):

        comparison["type"] = "seating"
        comparison["operator"] = "greater_than"

    return comparison


# ---------------------------------------------------------
# REFERENCE MODEL
# ---------------------------------------------------------

def find_reference_model(query, cars, original=None):
    """
    Finds a vehicle model explicitly mentioned in the query.

    A model must appear as a complete word/phrase.
    This prevents things like:

        sporty -> Sport

    from being interpreted as a vehicle reference.
    """

    matches = find_reference_models(query, cars, original=original)
    return matches[0]["model"] if matches else None


# Model names that are also everyday words ("city driving", "a sport car", "the venue").
AMBIGUOUS_MODEL_NAMES = {
    "city", "sport", "seal", "venue", "compass", "swift", "punch", "discovery", "defender",
    "cooper", "superb", "elevate", "aura", "carnival", "safari", "basalt", "amaze", "meridian",
}
_STRONG_CUES = re.compile(
    r"(?:than|like|vs\.?|versus|similar\s+to|compared\s+(?:to|with)|alternative\s+to|instead\s+of|rival\s+to)"
    r"\s*(?:the\s+|a\s+|an\s+)?$"
)


def _is_explicit_reference(model, start, end, query, original, brands):
    """Decide whether an everyday-word model name really refers to the car."""
    before = query[max(0, start - 40):start].rstrip()
    after = query[end:end + 25]
    if any(before.endswith(brand) for brand in brands):
        return True  # "Honda City", "Tata Safari"
    if _STRONG_CUES.search(before + " "):
        return True  # "cheaper than Swift", "like the Venue"
    if re.match(r"\s*(?:alternative|rival|or similar|vs\.?|versus|owner)", after):
        return True  # "City alternative"
    if original and len(original) == len(query) and start > 0:
        # A capitalised name mid-sentence ("I drive a Venue") is a deliberate proper noun.
        return original[start].isupper()
    return False


def find_reference_models(query, cars, original=None):
    """Find all catalog model mentions in order, preferring the longest name.

    Models whose names are everyday words only count when the context makes the reference
    explicit (brand name, comparison wording, or a capitalised proper noun).
    """
    if not cars or not isinstance(query, str):
        return []
    brands_by_model = {}
    for car in cars:
        if car.get("model") and car.get("brand"):
            brands_by_model.setdefault(car["model"].strip().lower(), set()).add(car["brand"].strip().lower())
    canonical_models = {
        car["model"].strip().lower(): car["model"]
        for car in cars if car.get("model")
    }
    models = sorted(
        {car.get("model") for car in cars if car.get("model")},
        key=len,
        reverse=True,
    )
    if not models:
        return []
    pattern = re.compile(
        r"(?<![a-z0-9])(?:" + "|".join(re.escape(model) for model in models)
        + r")(?![a-z0-9])",
        re.IGNORECASE,
    )
    found = []
    for match in pattern.finditer(query):
        name = match.group(0).strip().lower()
        if name in AMBIGUOUS_MODEL_NAMES and not _is_explicit_reference(
            name, match.start(), match.end(), query.lower(), original, brands_by_model.get(name, set())
        ):
            continue
        found.append({"model": canonical_models[name], "start": match.start(), "end": match.end()})
    return found


def extract_price_reference_comparisons(query, cars):
    """Associate nearby cheaper/costlier wording with each mentioned model."""
    refs = find_reference_models(query, cars)
    if not refs:
        return []
    lower_terms = (
        "less expensive than", "lower priced than", "lower price than",
        "cheaper than", "cheaper alternative", "budget alternative",
    )
    higher_terms = (
        "more expensive than", "higher priced than", "higher price than",
        "costlier than", "premium alternative",
    )
    comparisons = []
    for index, ref in enumerate(refs):
        segment_start = refs[index - 1]["end"] if index else 0
        segment = query[segment_start:ref["start"]].lower()
        operators = [
            (segment.rfind(term), "less_than")
            for term in lower_terms if term in segment
        ] + [
            (segment.rfind(term), "greater_than")
            for term in higher_terms if term in segment
        ]
        if operators:
            _, operator = max(operators, key=lambda pair: pair[0])
            comparisons.append({
                "type": "price",
                "operator": operator,
                "reference_model": ref["model"],
            })
    return comparisons

# ---------------------------------------------------------
# MAIN PARSER
# ---------------------------------------------------------

def parse_query(query, cars=None):
    original = query.strip() if isinstance(query, str) else ""
    query = original.lower()
    bounds = extract_price_bounds(query)
    if bounds:
        min_price, max_price, (start, end) = bounds
        # Read any separate ceiling ("above 50 lakh but under 80 lakh") outside the matched phrase.
        budget = max_price if max_price is not None else extract_budget(query[:start] + " " + query[end:])
    else:
        min_price, budget = None, extract_budget(query)

    features = extract_features(query)

    reference_model = find_reference_model(
        query,
        cars,
        original=original,
    )

    price_comparisons = extract_price_reference_comparisons(query, cars)

    comparison = extract_comparison(query)

    parsed = {

        "budget":
            budget,

        "min_price":
            min_price,

        "body_type":
            extract_body_type(query),

        "seats":
            extract_seats(query),

        "fuel_type":
            extract_fuel_type(query),

        "reference_model":
            reference_model,

        "comparison":
            comparison,

        "price_comparisons": price_comparisons,

        "intent":
            extract_intents(query),

        "vehicle_category":
            extract_vehicle_category(query),

        "transmission":
            extract_transmission(query),

        "turbo_required":
            features["turbo_required"],

        "drive_type":
            extract_drive_type(query),

        "min_bhp": extract_numeric_constraint(query, [r"(?:at least|minimum|min\.?|over)\s*(\d[\d,]*)\s*(?:bhp|hp)\b"]),

        "min_ncap": extract_numeric_constraint(query, [
            r"(?:at least|minimum|min\.?|over)\s*(\d)\s*[- ]?star(?:\s*ncap)?",
            r"\b(\d)\s*[- ]?star\s*(?:safety|ncap|crash|rated|rating|bharat ncap|global ncap)",
            r"\bncap\s*(?:rating\s*)?(?:of\s*)?(\d)\s*[- ]?stars?",
        ]),

        "min_airbags": extract_numeric_constraint(query, [r"(?:at least|minimum|min\.?|over)\s*(\d+)\s*airbags?"]),

        "adas_required":
            features["adas_required"],

        "sunroof_required":
            features["sunroof_required"],

        "ventilated_seats_required":
            features[
                "ventilated_seats_required"
            ],

        "camera_360_required":
            features[
                "camera_360_required"
            ],

        "ev_required":
            features["ev_required"],

        "min_range": extract_numeric_constraint(query, [r"(?:at least|minimum|min\.?|over)\s*(\d[\d,]*)\s*km\s*(?:range)?", r"range\s*(?:of|above|over)?\s*(\d[\d,]*)\s*km", r"(\d[\d,]*)\s*km\s*(?:of\s*)?range"]),

        "min_mileage": extract_numeric_constraint(query, [r"(?:at least|minimum|min\.?|over)\s*(\d+(?:\.\d+)?)\s*(?:km/?l|kmpl|mileage)"]),

        "min_boot_space": extract_numeric_constraint(query, [r"(?:at least|minimum|min\.?|over)\s*(\d+)\s*(?:litres?|liters?|l)\s*(?:boot|boot space)?"]),

        "min_ground_clearance": extract_numeric_constraint(query, [r"(?:at least|minimum|min\.?|over)\s*(\d+)\s*mm\s*(?:ground clearance)?"])
    }

    return parsed
