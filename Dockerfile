# Multi-stage build: the web front end (when web/package.json exists), then the Python app.
FROM node:22-slim AS web
WORKDIR /w
COPY web/ ./
RUN if [ -f package.json ]; then npm ci && npm run build; else mkdir -p dist; fi

FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends make \
    && rm -rf /var/lib/apt/lists/* && pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY api ./api
COPY scripts ./scripts
COPY data/gazetteer ./data/gazetteer
COPY Makefile ./
RUN uv sync --locked --no-dev
COPY --from=web /w/dist ./web/dist
# Mount runs/ and vendor/proving_ground/ at run time; give PURPOSEFIT_HMAC_KEY in the environment.
ENV HOST=0.0.0.0 PORT=8000 UV_NO_DEV=1
EXPOSE 8000
CMD ["make", "serve"]
