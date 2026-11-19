FROM python:3.11-slim

WORKDIR /app

# Pin dependencies and prevent network access after install
COPY pyproject.toml .
RUN pip install --no-cache-dir pydantic==2.10.4 numpy==2.2.1 pytest==8.3.4

COPY . .
RUN chmod +x scripts/check.sh

# Run check without network
CMD ["./scripts/check.sh"]
