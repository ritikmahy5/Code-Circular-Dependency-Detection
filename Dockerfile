# Use CUDA-enabled base image for GPU support (NVIDIA T4 compatible)
FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

# Install Python 3.11 and system dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3.11-distutils \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install pip for Python 3.11
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11 && \
    rm -f /usr/bin/python /usr/bin/pip && \
    ln -s /usr/bin/python3.11 /usr/bin/python && \
    ln -s /usr/local/bin/pip3.11 /usr/bin/pip || \
    ln -s $(python3.11 -m pip --version | awk '{print $NF}' | xargs dirname)/pip /usr/bin/pip

WORKDIR /app

# Set CUDA environment variables for GPU support
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Upgrade pip to latest version
RUN python3.11 -m pip install --upgrade pip setuptools wheel

# Install PyTorch with CUDA 12.1 support first (for GPU acceleration)
RUN python3.11 -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cu121 \
    torch torchvision torchaudio

# Install faiss-gpu (try available versions, fallback handled in code)
# Note: faiss-gpu may not have Python 3.11 wheels, so we'll try and handle gracefully
RUN python3.11 -m pip install --no-cache-dir faiss-gpu==1.7.2 || \
    python3.11 -m pip install --no-cache-dir faiss-gpu==1.7.1.post3 || \
    (echo "⚠️ faiss-gpu not available for Python 3.11, will use CPU FAISS" && \
     python3.11 -m pip install --no-cache-dir faiss-cpu>=1.7.4)

# Install remaining requirements (excluding torch and faiss which are already installed)
RUN grep -v "^torch" requirements.txt | grep -v "^faiss" | grep -v "^#" | grep -v "^$" > /tmp/requirements_filtered.txt && \
    python3.11 -m pip install --no-cache-dir -r /tmp/requirements_filtered.txt && \
    rm /tmp/requirements_filtered.txt

# Copy application code
COPY src/ ./src/
COPY knowledge_base/ ./knowledge_base/
COPY persistent_db/ ./persistent_db/
COPY setup.py .

# Note: lib/ directory not needed - visualization uses CDN links

# Install the package in development mode
RUN python3.11 -m pip install -e .

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
