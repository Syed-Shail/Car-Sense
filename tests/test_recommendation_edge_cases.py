import os
import json
import sys
import types
import unittest
from unittest.mock import patch
from pathlib import Path

import faiss
import joblib

from app.services.query_parser import extract_budget, parse_query
from app.services.llm_query_understanding import understand_query
from app.services.reference_resolver import resolve_reference, cars as reference_catalog
from app.services.hybrid_recommender import (
    SORT_OPTIONS,
    _best_variant,
    _capability_similarity,
    _intent_fit_score,
    _sort_recommendations,
    apply_filters,
    hybrid_recommend_with_suggestion,
)


def car_fixture(variants=None, **overrides):
    car = {
        "brand": "Example",
        "model": "Trail",
        "body_type": "SUV",
        "segment": "SUV",
        "seating_capacity": 5,
        "base_specs": {"fuel_type": "Petrol", "drive": "AWD"},
        "dimensions": {"boot_space": 400, "ground_clearance": 210},
        "ai": {
            "family_score": 7,
            "performance_score": 7,
            "city_score": 5,
            "luxury_score": 6,
            "offroad_score": 9,
            "safety_score": 8,
            "efficiency_score": 6,
        },
        "variants": variants if variants is not None else [
            {
                "variant_name": "Base",
                "pricing": {"ex_showroom": 1_000_000, "resale_value": "good"},
                "engine": {"transmission": "Automatic", "fuel_type": "Petrol", "drive": "AWD"},
                "safety": {"airbags": 6, "ncap": 5, "adas_level_2": False},
                "efficiency": {"arai": 15},
                "ev": {"is_ev": False, "range_km": 0},
                "features": {
                    "sunroof": False,
                    "ventilated_seats": False,
                    "camera_360": False,
                },
                "warranty": {"years": 3},
            }
        ],
    }
    car.update(overrides)
    return car


class BudgetParsingTests(unittest.TestCase):
    def test_indian_and_currency_budget_formats(self):
        cases = {
            "under 20 lakh": 2_000_000,
            "below 20 lakhs": 2_000_000,
            "budget of 25 lac": 2_500_000,
            "under 1.5 crore": 15_000_000,
            "under 1 crore 50 lakh": 15_000_000,
            "under ₹1,500,000": 1_500_000,
            "under Rs. 1,500,000": 1_500_000,
            "within INR 2,000,000": 2_000_000,
            "under 1,500,000": 1_500_000,
            "less than 20,00,000": 2_000_000,
            "under 1500000": 1_500_000,
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                self.assertEqual(parse_query(query)["budget"], expected)

    def test_ambiguous_or_invalid_budgets_do_not_become_prices(self):
        for query in ("under 15", "under 5 seats", "", None, 23, "under -15 lakh"):
            with self.subTest(query=query):
                self.assertIsNone(parse_query(query)["budget"])


class QueryUnderstandingTests(unittest.TestCase):
    def test_indirect_intents_and_singular_phrases(self):
        cases = {
            "a car for rough road driving": "offroad",
            "easy to park in the city": "city",
            "cheap to run": "efficiency",
            "protect my family": "safety",
            "sports car for weekend drives": "performance",
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                self.assertIn(expected, parse_query(query)["intent"])

    def test_unrelated_words_do_not_trigger_partial_intents(self):
        parsed = parse_query("A sporty car for breakfast runs")
        self.assertNotIn("offroad", parsed["intent"])
        self.assertNotIn("performance", parse_query("breakfast runs")["intent"])

    def test_feature_and_transmission_synonyms(self):
        parsed = parse_query("electric SUV, automatic, sunroof, ADAS, 360-degree camera")
        self.assertEqual(parsed["fuel_type"], "Electric")
        self.assertEqual(parsed["transmission"], "Automatic")
        self.assertTrue(parsed["sunroof_required"])
        self.assertTrue(parsed["adas_required"])
        self.assertTrue(parsed["camera_360_required"])

    def test_parser_handles_arbitrary_input_types_and_unicode(self):
        for query in (None, 0, [], {}, "🚙 4×4 rough-road SUV under ₹20 lakh"):
            with self.subTest(query=repr(query)):
                parsed = parse_query(query)
                self.assertIsInstance(parsed, dict)
                self.assertIn("budget", parsed)

    def test_parser_survives_generated_text_corpus(self):
        fragments = ["SUV", "electric", "₹", "1.5 crore", "rough road", "sports", "under", "7 seats", "\n", "🚙", "Fortuner"]
        for offset in range(150):
            query = " ".join(fragments[(index + offset) % len(fragments)] for index in range(offset % 7 + 1))
            with self.subTest(offset=offset):
                parsed = parse_query(query)
                self.assertIsInstance(parsed["intent"], list)

    def test_llm_failure_falls_back_to_deterministic_rules(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            parsed = understand_query("SUV under 15 lakh", [])
        self.assertEqual(parsed["budget"], 1_500_000)
        self.assertEqual(parsed["query_understanding"], "rules")

    def test_llm_cannot_override_explicit_budget_or_invent_invalid_fields(self):
        payload = json.dumps({
            "budget": 25_000_000,
            "seats": 99,
            "body_type": "Spaceship",
            "fuel_type": "Unobtanium",
            "transmission": "Warp drive",
            "intent": ["offroad"],
            "reference_model": "Unknown Model",
            "comparison": {"type": "price", "operator": "greater_than"},
        })
        client = types.SimpleNamespace(
            responses=types.SimpleNamespace(
                create=lambda **kwargs: types.SimpleNamespace(output_text=payload)
            )
        )
        fake_module = types.ModuleType("openai")
        fake_module.OpenAI = lambda: client
        catalog = [{"brand": "Toyota", "model": "Fortuner", "body_type": "SUV", "variants": []}]
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch.dict(sys.modules, {"openai": fake_module}):
            parsed = understand_query("SUV under 15 lakh", catalog)
        self.assertEqual(parsed["budget"], 1_500_000)
        self.assertIsNone(parsed["seats"])
        self.assertEqual(parsed["body_type"], "SUV")
        self.assertIsNone(parsed["fuel_type"])
        self.assertIsNone(parsed["transmission"])
        self.assertIsNone(parsed["reference_model"])

    def test_reference_names_are_whole_model_matches(self):
        catalog = [{"model": "Sport"}, {"model": "Fortuner Legender"}, {"model": "Fortuner"}]
        self.assertEqual(parse_query("a sporty SUV", catalog)["reference_model"], None)
        self.assertEqual(parse_query("costlier than Fortuner", catalog)["reference_model"], "Fortuner")
        self.assertEqual(parse_query("Fortuner Legender alternative", catalog)["reference_model"], "Fortuner Legender")

    def test_two_price_references_resolve_to_a_price_interval(self):
        query = "A car cheaper than a Toyota Fortuner but costlier than a Hyundai Creta"
        parsed = resolve_reference(parse_query(query, reference_catalog))
        self.assertEqual(parsed["reference_model"], "Fortuner")
        self.assertEqual(parsed["price_comparisons"], [
            {"type": "price", "operator": "less_than", "reference_model": "Fortuner"},
            {"type": "price", "operator": "greater_than", "reference_model": "Creta"},
        ])
        self.assertEqual(parsed["min_price"], 1_120_000)
        self.assertEqual(parsed["max_price"], 3_500_000)


class FilteringTests(unittest.TestCase):
    def test_feature_matching_selects_cheapest_eligible_variant(self):
        car = car_fixture(variants=[
            {"variant_name": "Base", "pricing": {"ex_showroom": 900_000}, "features": {"sunroof": False}},
            {"variant_name": "Sunroof", "pricing": {"ex_showroom": 1_100_000}, "features": {"sunroof": True}},
            {"variant_name": "Top", "pricing": {"ex_showroom": 1_300_000}, "features": {"sunroof": True}},
        ])
        self.assertEqual(_best_variant(car, {"sunroof_required": True})[0:2], (1_100_000, car["variants"][1]))
        self.assertEqual(len(apply_filters([car], budget=1_100_000, sunroof_required=True)), 1)
        self.assertEqual(apply_filters([car], budget=1_000_000, sunroof_required=True), [])

    def test_all_hard_variant_constraints_must_match_same_variant(self):
        car = car_fixture(variants=[
            {"variant_name": "Sunroof", "pricing": {"ex_showroom": 900_000}, "features": {"sunroof": True}, "engine": {"transmission": "Manual"}},
            {"variant_name": "Automatic", "pricing": {"ex_showroom": 1_100_000}, "features": {"sunroof": False}, "engine": {"transmission": "Automatic"}},
        ])
        self.assertIsNone(_best_variant(car, {"sunroof_required": True, "transmission": "automatic"})[1])

    def test_missing_or_malformed_variant_fields_are_skipped(self):
        car = car_fixture(variants=[None, {}, {"pricing": None}, {"pricing": {"ex_showroom": "unknown"}}])
        self.assertEqual(_best_variant(car, {})[1], None)

    def test_budget_comparison_and_physical_constraints(self):
        car = car_fixture()
        self.assertEqual(len(apply_filters([car], budget=1_000_000)), 1)
        self.assertEqual(apply_filters([car], budget=999_999), [])
        self.assertEqual(apply_filters([car], min_price=1_000_000), [])
        self.assertEqual(len(apply_filters([car], min_price=999_999)), 1)
        self.assertEqual(apply_filters([car], seats=7), [])
        self.assertEqual(apply_filters([car], min_ground_clearance=211), [])
        self.assertEqual(apply_filters([car], min_boot_space=401), [])

    def test_empty_reference_catalog_does_not_crash_comparison(self):
        with patch("app.services.reference_resolver.cars", [{"model": "Empty", "variants": []}]), patch(
            "app.services.reference_resolver.find_reference_car",
            return_value={"model": "Empty", "variants": []},
        ):
            parsed = {"reference_model": "Empty", "comparison": {"type": "price", "operator": "greater_than"}}
            self.assertNotIn("min_price", resolve_reference(parsed))


class RankingTests(unittest.TestCase):
    def test_offroad_intent_uses_catalog_fit_and_ground_clearance(self):
        high_clearance = {"offroad_score": 10, "performance_score": 10, "safety_score": 10, "ground_clearance": 291, "score": 0.5}
        crossover = {"offroad_score": 10, "performance_score": 10, "safety_score": 10, "ground_clearance": 180, "score": 0.99}
        self.assertEqual(_sort_recommendations([crossover, high_clearance], "recommended", priority="offroad")[0], high_clearance)
        self.assertEqual(_intent_fit_score(high_clearance, "offroad"), 10)

    def test_every_supported_sort_option_handles_ties_and_empty_values(self):
        rows = [
            {"price": 1_000_000, "score": 0.5, "seats": 5, "fuel_type": "Petrol", "transmission": None, "body_type": None},
            {"price": 1_000_000, "score": 0.5, "seats": 7, "fuel_type": "Diesel", "transmission": "Automatic", "body_type": "SUV"},
            {"price": 1_250_000, "score": 0.9, "seats": 5, "fuel_type": None, "transmission": "Manual", "body_type": "Sedan"},
        ]
        metric_names = {
            "arai_mileage", "ev_range_km", "warranty_years", "resale_quality",
            "safety_score", "performance_score", "luxury_score", "city_score",
            "offroad_score", "boot_space", "ground_clearance",
        }
        for row in rows:
            row.update({key: 0 for key in metric_names})
        for sort_by in SORT_OPTIONS:
            with self.subTest(sort_by=sort_by):
                ordered = _sort_recommendations(
                    rows, sort_by, budget=1_100_000,
                    preferred_fuel="Petrol", priority="offroad",
                )
                self.assertEqual(len(ordered), len(rows))


class CatalogArtifactTests(unittest.TestCase):
    def test_catalog_variants_prices_and_model_artifacts_are_consistent(self):
        root = Path(__file__).resolve().parents[1]
        catalog = json.loads((root / "data/processed/enhanced_vehicles.json").read_text(encoding="utf-8"))
        self.assertTrue(catalog)
        self.assertEqual(faiss.read_index(str(root / "data/processed/car_index.faiss")).ntotal, len(catalog))
        artifacts = joblib.load(root / "data/processed/ranker.pkl")
        known_bodies = set(artifacts["body_encoder"].classes_)
        for car in catalog:
            with self.subTest(model=car.get("model")):
                self.assertTrue(car.get("brand"))
                self.assertTrue(car.get("model"))
                self.assertIn(car.get("body_type"), known_bodies)
                self.assertTrue(car.get("variants"))
                for variant in car["variants"]:
                    price = variant.get("pricing", {}).get("ex_showroom")
                    self.assertIsInstance(price, (int, float))
                    self.assertGreater(price, 0)


class FlexibleSuggestionTests(unittest.TestCase):
    def test_reference_capability_similarity_uses_specs_and_ignores_price(self):
        reference = car_fixture(model="Reference")
        alternative = car_fixture(model="Alternative", variants=[{
            **car_fixture()["variants"][0],
            "pricing": {"ex_showroom": 500_000},
        }])
        self.assertEqual(_capability_similarity(alternative, reference), 100)

        weaker = car_fixture(
            model="Weaker", seating_capacity=4,
            dimensions={"boot_space": 100, "ground_clearance": 100},
            ai={
                "family_score": 2, "performance_score": 2, "city_score": 2,
                "luxury_score": 2, "offroad_score": 2, "safety_score": 2,
                "efficiency_score": 2,
            },
        )
        self.assertLess(_capability_similarity(weaker, reference), 100)

    def test_budget_flexible_pick_preserves_all_hard_requirements(self):
        from app.services import hybrid_recommender as service

        qualifying_variants = [{
            "variant_name": "Sunroof trim",
            "pricing": {"ex_showroom": 1_250_000, "resale_value": "good"},
            "engine": {"transmission": "Automatic", "fuel_type": "Petrol", "drive": "AWD"},
            "safety": {"airbags": 6, "ncap": 5},
            "efficiency": {"arai": 15}, "ev": {"is_ev": False},
            "features": {"sunroof": True}, "warranty": {"years": 3},
        }]
        regular = car_fixture(model="In budget", variants=[dict(qualifying_variants[0], pricing={"ex_showroom": 900_000})])
        flexible = car_fixture(model="Flexible", variants=qualifying_variants)
        wrong_feature = car_fixture(model="Wrong feature", variants=[dict(qualifying_variants[0], features={"sunroof": False})])
        with patch.object(service, "semantic_candidates", return_value=[regular, flexible, wrong_feature]):
            recommendations, suggestion = hybrid_recommend_with_suggestion(
                "sunroof automatic petrol SUV under 10 lakh",
                budget=1_000_000,
                body_type="SUV",
                priority="offroad",
                sort_by="budget_fit",
                fuel_type="Petrol",
                transmission="Automatic",
                sunroof_required=True,
            )
        self.assertEqual([item["model"] for item in recommendations], ["In budget"])
        self.assertEqual(suggestion["model"], "Flexible")
        self.assertEqual(suggestion["budget_relation"], "above")


class ApiEdgeCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.app import app
        app.config.update(TESTING=True)
        cls.client = app.test_client()

    def test_non_object_blank_and_oversized_requests_are_rejected(self):
        requests = [
            ([], 400),
            (None, 400),
            ({"query": 123}, 400),
            ({"query": "   "}, 400),
            ({"query": "x" * 601}, 400),
        ]
        for body, expected_status in requests:
            with self.subTest(body=repr(body)[:30]):
                response = self.client.post("/recommend", json=body)
                self.assertEqual(response.status_code, expected_status)

    def test_invalid_sort_falls_back_and_reference_comparison_returns_defender(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            with patch("app.routes.understand_query", return_value={
                "budget": None, "seats": None, "body_type": None, "intent": ["offroad"],
                "reference_model": None, "comparison": {},
            }), patch("app.routes.hybrid_recommend_with_suggestion", return_value=([], None)):
                response = self.client.post("/recommend", json={
                    "query": "A costlier alternative to the Toyota Fortuner for rough roads",
                    "sort_by": {"unexpected": "value"},
                })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["sorted_by"], "recommended")
        self.assertIsNone(payload["parsed_query"]["seats"])
        self.assertEqual(payload["recommendations"], [])


if __name__ == "__main__":
    unittest.main()
