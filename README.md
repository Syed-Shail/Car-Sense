# CarSense — AI vehicle recommendations for the Indian market

CarSense turns a natural-language car-shopping request into a ranked shortlist from a structured Indian-market vehicle catalog. The local pipeline combines query understanding, FAISS semantic candidate retrieval, attribute constraints, and a trained scikit-learn ranking model.

## How a recommendation is produced

1. The React client sends a natural-language `query` to `POST /recommend`.
2. Query understanding extracts budget, seating, body type, fuel, transmission, drivetrain, intent, reference model, comparison, and supported equipment/specification constraints. Indirect phrases such as “sports car,” “roadster,” “easy to park,” “cheap to run,” and “family hauler” map to catalog categories and recommendation intents. When `OPENAI_API_KEY` is configured, an LLM extraction step supplements the deterministic parser. Without it, the service works using rules alone.
3. A reference model mentioned by the user is resolved against the local catalog. Comparative requests such as “cheaper than Fortuner” become catalog-derived price constraints.
4. Sentence Transformer embeddings and the FAISS index retrieve semantically related vehicles. Structured filters apply the supported hard constraints.
5. The saved Random Forest ranker scores candidates for the selected intent and returns up to five recommendations with their catalog specifications and starting ex-showroom prices.

When a budget is provided, the primary shortlist first enforces it as a ceiling, then ranks eligible matches by price proximity (the closest available price below the ceiling comes first). A separate budget-flexible suggestion keeps the other stated hard requirements and favors the detected intent, while allowing a price above or below the stated budget.

The results page can re-sort the shortlist by best intent match, closest-to-budget price, price ascending or descending, seat count, fuel, transmission, body type, ARAI mileage, safety, performance, comfort/features, city use, off-road ability, boot space, ground clearance, EV range, warranty, or resale rating. Every ordering is applied after the same query filters. The flexible pick remains separate from that ordering.

The catalog currently contains 181 vehicle models from the checked-in processed data. Prices and specifications are sourced from the included dataset and are not live quotes. PostgreSQL can serve as the runtime catalog when configured; the bundled JSON catalog remains the local fallback.

## Run locally

Use Python 3.10+ and install the packages listed in `requirements.txt`. In one terminal, start the API:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

In a second terminal, start the React client:

```bash
cd web
npm install
npm run dev
```

Open the local Vite URL printed in the terminal. Vite proxies API requests to Flask on `127.0.0.1:5000`.

On first run, `sentence-transformers` may download `all-MiniLM-L6-v2`. The processed vehicle JSON, FAISS index, and ranker are checked into `data/processed/`.

To enable LLM-assisted extraction, set `OPENAI_API_KEY`. `OPENAI_MODEL` optionally selects a model; the default is `gpt-4o-mini`. If the key is missing or the LLM call fails, the deterministic parser remains available.

To use PostgreSQL for the catalog, set `DATABASE_URL` to a PostgreSQL connection string, then load the processed catalog:

```bash
export DATABASE_URL='postgresql://user:password@localhost:5432/carsense'
python scripts/postgres_uploader.py
```

The loader preserves catalog order so its rows remain aligned with the checked-in FAISS index. If PostgreSQL is unset or unavailable, the app reads the bundled JSON catalog.

## Tests

Run the parser, filter, ranking, catalog integrity, LLM fallback, and API edge-case suite with:

```bash
python -m unittest discover -s tests -v
```

## API

`GET /health` returns `{"status":"ok"}` when the app is running.

`POST /recommend` accepts a query and an optional `sort_by` key (the page sends the selected sort choice):

```json
{"query":"A safe 7-seater SUV under 25 lakh, automatic, with a 360 camera"}
```

Example with an ordering:

```json
{"query":"A safe 7-seater SUV under 25 lakh, automatic, with a 360 camera", "sort_by":"mileage"}
```

Successful response shape:

```json
{
  "parsed_query": {"budget": 2500000, "seats": 7},
  "recommendations": [
    {
      "brand": "Example",
      "model": "Example model",
      "score": 0.84,
      "price": 2000000,
      "body_type": "SUV",
      "seats": 7,
      "fuel_type": "Petrol",
    }
  ]
}
```

An empty or missing query returns HTTP 400. LLM-assisted query extraction sends the user's query to the configured OpenAI API; omit `OPENAI_API_KEY` for local rules-only processing.

## Rebuild the local data artifacts

Run these commands from the repository root after changing `data/raw/vehicles.csv`:

```bash
python scripts/csv_cleaner.py
python scripts/feature_engineering.py
python scripts/build_embeddings.py
python scripts/generate_training_data.py
python -m app.services.train_ranker
```

Training labels are generated from the project's heuristic preference scoring, not user interaction or a human-labeled relevance dataset. The resulting Random Forest demonstrates a trainable ranking stage; its scores should not be interpreted as calibrated probabilities of purchase or recommendation quality.

## Project structure

```text
app/                 Flask API and query/retrieval/ranking services
data/raw/            Source vehicle CSV
data/processed/      Cleaned catalog, engineered features, FAISS index, ranker
scripts/             Data preparation, feature engineering, artifact builders
run.py               Local application entry point
```

## Scope and current limitations

- This repository implements the Flask API, local catalog pipeline, FAISS retrieval, deterministic query parsing, optional OpenAI extraction, hard filters, and Random Forest reranking.
- The repository includes a React client and an optional PostgreSQL catalog pipeline. It does not include Docker configuration, AWS infrastructure, or measured 10K-request/day capacity; deployment is outside this local project implementation.
- The checked-in catalog and heuristic training labels limit recommendation quality. Verify vehicle details and prices with manufacturers or dealers before making a purchase decision.
