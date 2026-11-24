# CarSense — AI vehicle recommendations for the Indian market

CarSense turns a natural-language car-shopping request into a ranked shortlist from a structured Indian-market vehicle catalog. The local pipeline combines query understanding, FAISS semantic candidate retrieval, attribute constraints, and a trained scikit-learn ranking model.

## Results

Measured on hand-labelled queries ([`evaluation/`](evaluation/)) and an HTTP load test ([`loadtest/`](loadtest/)), on an Apple M5 laptop.

**Query understanding**: every structured field is compared with its label; fields the user didn't mention must stay empty.

| Query set | Queries | Field accuracy | Constraint F1 | Queries fully understood |
|---|---|---|---|---|
| Development, before the parser fixes | 58 | 98.3% | 0.936 | 75.9% |
| Development, after | 58 | 100% | 1.000 | 100% |
| **Held-out** (written separately, never used for tuning) | 30 | **99.6%** | **0.987** | **93.3%** |

**Recommendations**: every car in the primary shortlist is checked against the user's stated budget, minimum price, seats, body type, fuel and gearbox.

| | Before | After |
|---|---|---|
| Returned cars meeting every stated constraint (development) | 83.6% | **100%** |
| Returned cars meeting every stated constraint (held-out) | – | **100%** |
| Median / p95 request latency | 95 ms / 1,287 ms | **23 ms / 45 ms** |

**Throughput** (Gunicorn, 1 worker × 4 threads, the Docker image's settings; 3,815 requests replaying the labelled queries):

| Concurrent users | Requests/s | p50 | p95 | Errors |
|---|---|---|---|---|
| 1 | 44.2 | 23 ms | 27 ms | 0 |
| 4 | 48.7 | 79 ms | 115 ms | 0 |
| 16 | 48.2 | 329 ms | 380 ms | 0 |

About 48 requests/s on a single worker is roughly **4.2 million requests per day**. On AWS the service autoscales on CPU from 1 to 4 tasks (see [Deploy to AWS](#deploy-to-aws)).

### What the evaluation found and fixed

- **Seat counts** like "7-seater", "seven seater", "seats 8" and "family of six" were missed. The seat parser now handles hyphens, number words and these phrasings.
- **Everyday words matched car names.** "City driving", "a sport car" and "the venue of my wedding" were read as the Honda City, the Sport and the Hyundai Venue. Models whose names are common words now need explicit context: the brand name ("Honda City"), comparison wording ("cheaper than Swift", "like the Venue") or a capitalised proper noun.
- **Price ranges** ("between 60 lakh and 1 crore", "between 20 and 30 lakh") and **minimums** ("above 50 lakh") were turned into a single ceiling. They now set both bounds, or only a minimum.
- **Safety ratings and EV range** without "at least" ("5-star safety rating", "500 km range") are now understood.
- **Gearbox filtering.** iMT, a clutchless *manual*, was offered to people asking for an automatic, while PDK (dual-clutch) and single-speed EV gearboxes were wrongly excluded.
- **Latency.** The Random Forest ranker was called once per candidate car (181 calls per request). Scoring all candidates in one batched call gives identical scores and cut ranking from 1,254 ms to 14 ms.

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

## Run with Docker

Build the image from the repository root:

```bash
docker build -t carsense .
```

Start the container:

```bash
docker run --rm -p 5000:5000 carsense
```

Open `http://localhost:5000`. The same container serves the React client and Flask API; `/health` is the health-check endpoint. The image build downloads the Sentence Transformer model so semantic retrieval is available when the container starts. This requires network access during the first build and makes the image larger.

Optional integrations can be configured at runtime with `OPENAI_API_KEY`, `OPENAI_MODEL`, or `DATABASE_URL`. Without them, the deterministic parser and bundled JSON catalog are used.

## Tests

Run the parser, filter, ranking, catalog integrity, LLM fallback, regression and API edge-case suite (28 tests) with:

```bash
python -m unittest discover -s tests -v
```

## Evaluation and load testing

```bash
python -m evaluation.run_eval      # query understanding + recommendation constraints, both query sets
python loadtest/load_test.py --url http://127.0.0.1:5000 --seconds 20
```

The evaluation writes `evaluation/results.json`, including every field-level error. The load test replays the 88 labelled queries at 1, 4, 8 and 16 concurrent users against a running server (start it with the Gunicorn command from the Dockerfile) and writes `loadtest/results.json`.

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs the unit tests and the evaluation on every push, fails if held-out constraint F1 drops below 0.95 or constraint satisfaction drops below 98%, and builds the production Docker image.

## Deploy to AWS

[`infra/aws/`](infra/aws/) contains Terraform for ECR, an ECS Fargate service behind an Application Load Balancer (`/health` checks, CPU autoscaling from 1 to 4 tasks, circuit-breaker rollback), CloudWatch logs, Secrets Manager for `OPENAI_API_KEY` and `DATABASE_URL`, and an optional encrypted RDS PostgreSQL catalog. [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) builds, pushes and rolls out a new image on demand using GitHub OIDC (no long-lived AWS keys). Step-by-step instructions are in [`infra/aws/README.md`](infra/aws/README.md).

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
evaluation/          Labelled development and held-out queries, evaluation runner and results
loadtest/            HTTP load test and results
infra/aws/           Terraform for ECR, ECS Fargate, ALB, autoscaling, Secrets Manager and RDS
.github/workflows/   CI (tests, evaluation quality gate, Docker build) and manual AWS deploy
tests/               Unit and regression tests
run.py               Local application entry point
```

## Limitations

- Ranking labels are generated from the project's heuristic preference scores, not from user clicks or human relevance judgements, so the Random Forest score is a ranking signal, not a calibrated purchase probability.
- Known held-out misses: plural body types ("SUVs") and "more fuel efficient" are not yet recognised. They are left unfixed so the held-out set stays untouched.
- Prices and specifications come from the bundled dataset, not live quotes. Verify details with a dealer before buying.
