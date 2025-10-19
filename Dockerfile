# === Stage 1: Backend Dockerfile ===
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy dependency files first (for layer caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy your full app code
COPY . .

# Expose the backend port
EXPOSE 8000

# Start FastAPI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
