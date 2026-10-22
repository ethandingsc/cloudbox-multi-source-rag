FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ANONYMIZED_TELEMETRY=False \
    HF_HOME=/app/.cache/huggingface

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY data ./data
COPY scripts ./scripts
COPY api.py worker.py ./

# The demo knowledge base is static. Bake its 590-chunk index into the image
# so each API/worker replica has its own local ChromaDB copy.
RUN python scripts/ingest.py
RUN python -c "from src.rerank import Reranker; Reranker()"

# Both sentence-transformer models are now cached in the image. Runtime must
# not depend on Hugging Face availability.
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=30s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=25)" || exit 1
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
