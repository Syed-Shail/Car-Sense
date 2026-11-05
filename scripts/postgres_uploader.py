"""Load the processed catalog into PostgreSQL while preserving FAISS order."""
import json
import os
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data/processed/enhanced_vehicles.json"


def upload_catalog(database_url):
    with DATA_FILE.open("r", encoding="utf-8") as source:
        cars = json.load(source)

    with psycopg.connect(database_url) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS vehicle_catalog (
                catalog_position INTEGER PRIMARY KEY,
                brand TEXT NOT NULL,
                model TEXT NOT NULL,
                payload JSONB NOT NULL,
                UNIQUE (brand, model)
            )
        """)
        connection.executemany("""
            INSERT INTO vehicle_catalog (catalog_position, brand, model, payload)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (catalog_position) DO UPDATE SET
                brand = EXCLUDED.brand,
                model = EXCLUDED.model,
                payload = EXCLUDED.payload
        """, [
            (position, car["brand"], car["model"], Jsonb(car))
            for position, car in enumerate(cars)
        ])
        connection.execute(
            "DELETE FROM vehicle_catalog WHERE catalog_position >= %s",
            (len(cars),),
        )
    print(f"Loaded {len(cars)} vehicles into PostgreSQL.")


if __name__ == "__main__":
    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("Set DATABASE_URL before loading the catalog.")
    upload_catalog(url)
