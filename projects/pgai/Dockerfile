FROM python:3.12-slim AS build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/usr/local/
WORKDIR /build
COPY --from=ghcr.io/astral-sh/uv:0.4.29 /uv /uvx /bin/

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-install-project --no-dev

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

RUN useradd -ms /bin/bash pgaiuser

# Copy installed dependencies from build stage
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

COPY pyproject.toml /app/
COPY pgai /app/pgai

USER pgaiuser

ENTRYPOINT ["python", "-m", "pgai", "vectorizer", "worker"]
CMD ["-c", "4"]