# Build the React client separately so Node.js is not part of the runtime image.
FROM node:22-bookworm-slim AS frontend-build

WORKDIR /src/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Flask serves both the recommendation API and the built React client.
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/huggingface \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    TOKENIZERS_PARALLELISM=false

WORKDIR /app

# FAISS and other numeric libraries need the GNU OpenMP runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
# Select PyTorch's CPU-only wheel first so Linux builds do not pull CUDA
# libraries that this CPU inference container cannot use.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Cache the model in the image because the application loads it in offline mode.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY app/ ./app/
COPY run.py ./run.py
COPY data/processed/enhanced_vehicles.json ./data/processed/enhanced_vehicles.json
COPY data/processed/car_index.faiss ./data/processed/car_index.faiss
COPY data/processed/ranker.pkl ./data/processed/ranker.pkl
COPY --from=frontend-build /src/web/dist/ ./web/dist/

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=3)"]

CMD ["gunicorn", "--bind=0.0.0.0:5000", "--workers=1", "--threads=4", "--timeout=120", "app.app:app"]
