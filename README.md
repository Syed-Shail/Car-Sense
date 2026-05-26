# AutoSense India

A vehicle discovery website for the Indian market with:

- searchable vehicle catalog
- filters for budget, body type, fuel, and seating
- three-car comparison table
- questionnaire-based recommendations
- AI chat endpoint backed by OpenAI's Responses API when `OPENAI_API_KEY` is present
- local fallback recommender when no API key is configured

## Run

```bash
node server.js
```

Open `http://localhost:4173`.

## Strong AI Mode

Set an OpenAI API key before starting the server:

```bash
OPENAI_API_KEY=your_key_here node server.js
```

The server defaults to `gpt-5.5`. Override it with:

```bash
OPENAI_MODEL=gpt-5.5 OPENAI_API_KEY=your_key_here node server.js
```

## Data

The seed catalog lives in `data/vehicles.json`. It is designed to be expanded with more models,
city-level on-road prices, dealer availability, service-cost data, and images.
