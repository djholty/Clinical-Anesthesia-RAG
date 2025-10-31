#!/bin/bash
# Start FastAPI server with proper reload exclusions
# This excludes .venv, __pycache__, and other non-source directories from file watching

uvicorn app.main:app \
    --reload \
    --reload-exclude '.venv/*' \
    --reload-exclude '*.pyc' \
    --reload-exclude '__pycache__/*' \
    --reload-exclude '*.log' \
    --reload-exclude '.git/*' \
    --reload-exclude 'data/*' \
    --host 127.0.0.1 \
    --port 8000

