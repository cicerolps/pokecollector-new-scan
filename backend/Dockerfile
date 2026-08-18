FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    wget \
    gnupg \
    lsb-release \
    gcc \
    && install -d /etc/apt/keyrings \
    && wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /etc/apt/keyrings/postgresql.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/postgresql.gpg] http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-18 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Local card scanner: EasyOCR model weights are a static asset, baked in at
# build time so the container never needs network access to load them —
# same reasoning as poke-collector-v2's Dockerfile. The card catalogue and
# its hash bank (scripts/backfill_card_hashes.py) are the opposite: dynamic
# data that lives in the DB/volume, never in the image.
ENV EASYOCR_MODEL_DIR=/opt/easyocr-models
RUN mkdir -p ${EASYOCR_MODEL_DIR} \
    && python -c "import easyocr; easyocr.Reader(['en'], model_storage_directory='${EASYOCR_MODEL_DIR}', download_enabled=True)"

COPY VERSION /app/VERSION
COPY backend/ .

RUN mkdir -p /app/backups /app/debug /app/data/pokedex-images/sprites /app/data/pokedex-images/artwork

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
