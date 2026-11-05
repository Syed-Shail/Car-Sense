"""Load the FAISS-aligned catalog from PostgreSQL or the local JSON artifact."""
import json
import logging
import os
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)
DATA_FILE = Path(__file__).resolve().parents[2] / "data/processed/enhanced_vehicles.json"


def _enrich_verified_features(cars):
    """Fill known sunroof omissions in the source catalog for eligible trims.

    The checked-in source currently records ``sunroof: false`` for every one
    of its 738 variant rows. Hyundai's official 2026 Exter trim table lists an
    electric sunroof from HX4+ upward. These legacy catalog trim names identify
    the corresponding sunroof-equipped Exter trims represented in this data.
    """
    exter_sunroof_trims = {"sx", "sx (o)", "sx (o) connect", "sx amt"}
    for car in cars:
        if car.get("brand", "").lower() != "hyundai" or car.get("model", "").lower() != "exter":
            continue
        for variant in car.get("variants", []):
            if str(variant.get("variant_name", "")).strip().lower() in exter_sunroof_trims:
                variant.setdefault("features", {})["sunroof"] = True
    return cars


@lru_cache(maxsize=1)
def load_catalog():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        try:
            import psycopg
            with psycopg.connect(database_url) as connection:
                rows = connection.execute(
                    "SELECT payload FROM vehicle_catalog ORDER BY catalog_position"
                ).fetchall()
            if rows:
                return _enrich_verified_features([row[0] for row in rows])
            logger.warning("PostgreSQL catalog is empty; using the bundled catalog.")
        except Exception as exc:
            logger.warning("Could not load PostgreSQL catalog (%s); using bundled data.", exc)
    with DATA_FILE.open("r", encoding="utf-8") as source:
        return _enrich_verified_features(json.load(source))
