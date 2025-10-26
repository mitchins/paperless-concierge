FROM python:3.11-slim

WORKDIR /app

# Install system dependencies and git (needed for setuptools_scm)
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy git metadata first (needed for setuptools_scm versioning)
COPY .git/ ./.git/

# Copy pyproject.toml and source code
COPY pyproject.toml .
COPY src/ ./src/

# Install the package
RUN pip install --no-cache-dir . && \
    rm -rf .git && \
    mkdir -p /app/logs && chmod 777 /app/logs

# Create a non-root user for security
RUN useradd -m -u 1000 concierge && chown -R concierge:concierge /app
USER concierge

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the bot using the installed console script
CMD ["paperless-concierge"]
