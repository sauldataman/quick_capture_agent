# Quick Capture Agent - Docker Image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY src/ src/
COPY config/ config/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Create directories for data persistence
RUN mkdir -p /app/data/knowledge

# Environment variables (override these at runtime)
ENV TELEGRAM_BOT_TOKEN=""
ENV ANTHROPIC_API_KEY=""
ENV KNOWLEDGE_BASE_PATH="/app/data/knowledge"

# Expose port for webhook mode (optional)
EXPOSE 8443

# Default command: run Telegram bot
CMD ["python", "-m", "quick_capture_agent.main", "bot", "--vault", "/app/data/knowledge"]
