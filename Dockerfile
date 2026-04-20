# Microsoft's Playwright base image ships Chromium + all OS deps preinstalled.
# Tag matches the playwright Python package version we use locally (1.58.0).
# 'noble' = Ubuntu 24.04 with Python 3.12; 'jammy' (22.04) is stuck at 3.10
# and our pyproject requires >=3.11 (for stdlib tomllib).
FROM mcr.microsoft.com/playwright/python:v1.58.0-noble

WORKDIR /app

# Copy package metadata first for a better build-cache layer
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install runtime deps only (no [dev]). --no-cache-dir keeps the image smaller.
RUN pip install --no-cache-dir .

# Drop privileges: Microsoft's image ships a non-root 'pwuser'.
USER pwuser

# Cloud Run Job invokes this on schedule; exit code is the job result.
CMD ["python", "-m", "homebase_sync"]
