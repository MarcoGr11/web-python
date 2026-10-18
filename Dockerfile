# --- builder: compilers + headers, builds wheels for every dependency ---
FROM python:3.13-slim AS builder

# psycopg2-binary ships prebuilt wheels for most platforms, but keep build
# tools as a fallback in case pip has to compile it for the target arch.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# --- runtime: slim image with only the installed wheels and the code ---
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN --mount=type=bind,from=builder,source=/wheels,target=/wheels \
    pip install --no-cache-dir --no-index /wheels/*.whl

RUN useradd --create-home --uid 1000 app

WORKDIR /app
COPY --chown=app:app src/ src/

USER app
WORKDIR /app/src
