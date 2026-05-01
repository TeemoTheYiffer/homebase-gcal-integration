# Microsoft's Playwright base image ships Chromium + all OS deps preinstalled.
# IMPORTANT: this tag MUST match the pinned playwright version in pyproject.toml.
# Mismatch -> "Executable doesn't exist at /ms-playwright/..." at runtime.
# 'noble' = Ubuntu 24.04 with Python 3.12; 'jammy' (22.04) is stuck at 3.10.
FROM mcr.microsoft.com/playwright/python:v1.59.0-noble

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
