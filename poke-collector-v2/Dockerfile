# syntax=docker/dockerfile:1

# ---- builder: resolve deps into a venv, separate from the runtime image ----
FROM python:3.12-slim AS builder

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ---- runtime ----
FROM python:3.12-slim AS runtime

# util-linux provides setpriv, used by entrypoint.sh to drop from root to
# PUID/PGID without pulling in an extra gosu/su-exec binary.
RUN apt-get update \
    && apt-get install -y --no-install-recommends util-linux \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 1000 appuser \
    && useradd -u 1000 -g appuser -M -s /usr/sbin/nologin appuser

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    EASYOCR_MODULE_PATH=/opt/easyocr-models

# Static asset baked into the image at build time: EasyOCR model weights.
# NEVER the card catalog/hash DB — that is dynamic, lives in the /app/data
# volume, and is populated by the sync job (see PROJECT_SPEC.md 4.0).
RUN mkdir -p ${EASYOCR_MODULE_PATH} \
    && python -c "import easyocr; easyocr.Reader(['en'], model_storage_directory='${EASYOCR_MODULE_PATH}', download_enabled=True)" \
    && chown -R appuser:appuser ${EASYOCR_MODULE_PATH}

WORKDIR /app
COPY app ./app
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN mkdir -p /app/data && chown -R appuser:appuser /app

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
