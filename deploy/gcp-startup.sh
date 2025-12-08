#!/bin/bash
# GCP Startup Script for Circular Dependency Detective
# This script runs when the GCP instance starts

set -e

echo "Starting Circular Dependency Detective on GCP..."

# Update system packages
apt-get update -y

# Install Docker if not already installed
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
fi

# Install Docker Compose if not already installed
if ! command -v docker-compose &> /dev/null; then
    echo "Installing Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# Navigate to application directory (adjust path as needed)
cd /opt/cdd || cd /home/cdd || cd /app

# Pull latest code if using git
if [ -d .git ]; then
    git pull || true
fi

# Start services with Docker Compose
echo "Starting Docker containers..."
docker-compose up -d

# Wait for services to be healthy
echo "Waiting for services to start..."
sleep 30

# Check if Streamlit is running
if curl -f http://localhost:8501/_stcore/health; then
    echo "✅ Streamlit is running on port 8501"
else
    echo "⚠️ Streamlit health check failed"
fi

echo "Deployment complete!"
echo "Access the application at: http://$(curl -s ifconfig.me):8501"

