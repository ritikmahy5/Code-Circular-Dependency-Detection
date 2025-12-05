FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY knowledge_base/ ./knowledge_base/
COPY setup.py .

# Install the package
RUN pip install -e .

# Default command
CMD ["python", "-m", "src.cli", "--help"]
