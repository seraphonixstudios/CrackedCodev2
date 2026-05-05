# CrackedCode Docker Image
# Build: docker build -t crackedcode .
# Run:   docker run -p 8080:8080 -e OLLAMA_HOST=http://host.docker.internal:11434 crackedcode

FROM python:3.11-slim

LABEL maintainer="CrackedCode Team"
LABEL version="2.7.8"
LABEL description="CrackedCode - Local AI Coding Assistant"

# Prevent Python from writing pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY assets/ ./assets/
COPY config.json .
COPY test_system.py .
COPY README.md .
COPY AGENTS.md .
COPY WHITE_PAPER.md .

# Create directories for persistence
RUN mkdir -p .crackedcode/memory .crackedcode/metrics schedules plugins mcp_servers logs

# Expose API port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/ || exit 1

# Default command: run API server
CMD ["python", "-m", "src.main", "api", "--host", "0.0.0.0", "--port", "8080"]
