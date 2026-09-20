FROM python:3.13-slim

# psycopg2-binary ships prebuilt wheels for most platforms, but keep build
# tools as a fallback in case pip has to compile it for the target arch.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

WORKDIR /app/src
