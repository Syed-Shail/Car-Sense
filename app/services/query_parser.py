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
        "sporty",
        "fast",
        "powerful",
        "performance",
        "quick"
    ],

    "family": [
        "family",
        "family car",
        "family vehicle"
    ],

    "offroad": [
        "offroad",
        "off-road",
        "off roading",
        "offroading",
        "rugged",
        "rough roads",
        "bad roads",
        "4x4"
    ],

    "efficiency": [
        "fuel efficient",
        "fuel-efficient",
        "good mileage",
        "high mileage",
        "fuel economy",
        "economical"
    ],

    "luxury": [
        "luxury",
        "luxurious",
        "premium"
    ],

    "city": [
        "city",
        "city driving",
        "urban"
    ]
}


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def contains_any(text, terms):
    """
    Returns True if any term occurs in the text.
    """
    return any(term in text for term in terms)


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

    # Indian lakh format
    lakh_match = re.search(
        r'(\d+(?:\.\d+)?)\s*(?:lakh|lakhs|lac|l)\b',
        query
    )

    if lakh_match:
        value = float(lakh_match.group(1))
        return int(value * 100000)

    # Indian crore format
    crore_match = re.search(
        r'(\d+(?:\.\d+)?)\s*(?:crore|crores|cr)\b',
        query
    )

    if crore_match:
        value = float(crore_match.group(1))
        return int(value * 10000000)

    # Explicit rupee amounts
    rupee_match = re.search(
        r'(?:₹|rs\.?|inr)\s*(\d[\d,]*)',
        query
    )

    if rupee_match:
        value = rupee_match.group(1).replace(",", "")
        return int(value)

    return None


# ---------------------------------------------------------
# SEATS
# ---------------------------------------------------------

def extract_seats(query):
    patterns = [
        r'(\d+)\s*(?:seater|seaters|seats)',
        r'for\s+(\d+)\s*(?:people|passengers)',
        r'(\d+)\s*people',
        r'(\d+)\s*passengers'
    ]

    for pattern in patterns:

        match = re.search(pattern, query)

        if match:
            return int(match.group(1))

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

def find_reference_model(query, cars):
    """
    Finds a vehicle model explicitly mentioned in the query.

    A model must appear as a complete word/phrase.
    This prevents things like:

        sporty -> Sport

    from being interpreted as a vehicle reference.
    """

    if not cars:
        return None

    query = query.lower()

    models = set()

    for car in cars:
        model = car.get("model")

        if model:
            models.add(model)

    # Longest models first
    models = sorted(
        models,
        key=len,
        reverse=True
    )

    for model in models:

        model_lower = model.lower().strip()

        # Escape model name so regex treats it literally
        pattern = r'\b' + re.escape(model_lower) + r'\b'

        if re.search(pattern, query):
            return model

    return None

# ---------------------------------------------------------
# MAIN PARSER
# ---------------------------------------------------------

def parse_query(query, cars=None):

    query = query.lower().strip()

    features = extract_features(query)

    reference_model = find_reference_model(
        query,
        cars
    )

    comparison = extract_comparison(query)

    parsed = {

        "budget":
            extract_budget(query),

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

        "intent":
            extract_intents(query),

        "transmission":
            extract_transmission(query),

        "turbo_required":
            features["turbo_required"],

        "drive_type":
            extract_drive_type(query),

        "min_bhp":
            None,

        "min_ncap":
            None,

        "min_airbags":
            None,

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

        "min_range":
            None,

        "min_mileage":
            None,

        "min_boot_space":
            None,

        "min_ground_clearance":
            None
    }

    return parsed