#!/bin/bash
# GCP VM startup script for Circular Dependency Detective

set -e

echo "=== Setting up Circular Dependency Detective ==="

# Update system
apt-get update
apt-get install -y docker.io docker-compose git

# Start Docker
systemctl start docker
systemctl enable docker

# Clone repository (replace with your repo URL)
cd /opt
if [ ! -d "circular-dependency-detective" ]; then
    git clone https://github.com/YOUR_REPO/circular-dependency-detective.git
fi
cd circular-dependency-detective

# Pull Ollama model
docker run -d --name ollama-setup ollama/ollama
sleep 10
docker exec ollama-setup ollama pull codellama:13b
docker stop ollama-setup
docker rm ollama-setup

# Start services
cd deploy
docker-compose up -d

echo "=== Setup complete ==="
echo "Services running on:"
echo "  - Ollama: http://localhost:11434"
echo "  - ChromaDB: http://localhost:8000"
