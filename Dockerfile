FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY gemini_web2api/ ./gemini_web2api/
COPY config.example.json ./config.json

# Expose port
EXPOSE 8081

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8081/', timeout=5)" || exit 1

# Run
CMD ["python", "-m", "gemini_web2api", "--config", "/app/config.json"]
