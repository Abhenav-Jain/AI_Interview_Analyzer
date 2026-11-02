# syntax=docker/dockerfile:1.7
# ---------- 1) build the React app (also fetches the face model) ----------
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json* ./
COPY frontend/scripts ./scripts
# the build must fail loudly if the face model cannot be downloaded
ENV REQUIRE_FACE_MODEL=1
RUN npm ci --no-audit --no-fund
COPY frontend/ .
RUN npm run build

# ---------- 2) runtime ----------
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 \
    APP_ENV=production LOG_JSON=1 DATA_DIR=/data MODEL_DIR=/models \
    FRONTEND_DIST=/app/frontend_dist HF_HOME=/models/hf
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install -r requirements.txt

# bake the speech model into the image so the first request is never a download
ARG WHISPER_MODEL=small.en
ENV WHISPER_MODEL=${WHISPER_MODEL}
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('${WHISPER_MODEL}', device='cpu', compute_type='int8', download_root='/models')"

COPY backend/app ./app
COPY --from=web /web/dist ./frontend_dist

RUN useradd -m -u 10001 app && mkdir -p /data && chown -R app /data /models
USER app
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/ready', timeout=4).status==200 else 1)"

# One worker on purpose: the speech model is memory-heavy and live sessions are
# bound to a process. Scale horizontally with more containers instead.
CMD ["sh", "-c", "uvicorn app.main:get_app --factory --host 0.0.0.0 --port ${PORT:-8000} --ws-max-size 1048576 --proxy-headers --forwarded-allow-ips='*'"]
