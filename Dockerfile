FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Cloud Run injects PORT env var — do not hardcode it
EXPOSE 8080

# Use shell form so $PORT is expanded at runtime
CMD exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}