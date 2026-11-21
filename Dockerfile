FROM python:3.11-slim

WORKDIR /app

# Resolve pinned dependencies once; runtime verification works without a network.
COPY pyproject.toml .
RUN pip install --no-cache-dir pydantic==2.10.4 numpy==2.2.1 pytest==8.3.4

COPY . .
RUN pip install --no-cache-dir -e '.[dev]' \
    && sed -i 's/\r$//' scripts/check.sh \
    && chmod +x scripts/check.sh

CMD ["./scripts/check.sh"]
