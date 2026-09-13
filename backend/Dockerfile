# Use Python 3.11 slim as the base image for a small footprint
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Install system dependencies:
# - git: Required by GitPython to clone repositories
# - build-essential & python3-dev: Needed for compiling some Python packages (e.g. hnswlib for ChromaDB)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend source code
COPY . .

# Create the directories for persistent/temporary storage
RUN mkdir -p /app/chroma_db /app/repositories && \
    chmod -R 777 /app/chroma_db /app/repositories

# Start the FastAPI application.
# Render automatically injects the $PORT environment variable. If it's missing, default to 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
