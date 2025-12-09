# Use standard Python base image (CPU-only)
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# No GPU environment variables needed (CPU-only)

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Upgrade pip to latest version
RUN pip install --upgrade pip setuptools wheel

# Install all requirements (CPU-only)
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY knowledge_base/ ./knowledge_base/
COPY persistent_db/ ./persistent_db/
COPY setup.py .

# Note: lib/ directory not needed - visualization uses CDN links

# Install the package in development mode
RUN pip install -e .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV STREAMLIT_SERVER_HEADLESS=true

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Run Streamlit web app
CMD ["streamlit", "run", "src/web/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
