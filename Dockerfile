# === Stage 1: Backend Dockerfile ===
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy dependency files first (for layer caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY app ./app
COPY monitoring ./monitoring
COPY templates ./templates

# Create necessary directories
RUN mkdir -p uploads data/ingested_documents data/chroma_db data/pdfs

# Expose the backend port
EXPOSE 8000

# Start FastAPI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
