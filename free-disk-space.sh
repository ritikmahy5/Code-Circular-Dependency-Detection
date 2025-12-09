#!/bin/bash
# Script to free up disk space on GCP VM

echo "🧹 Freeing up disk space..."

# Clean Docker
echo "1. Cleaning Docker..."
docker system prune -a -f --volumes

# Remove old logs
echo "2. Cleaning logs..."
sudo journalctl --vacuum-time=1d

# Clean apt cache
echo "3. Cleaning apt cache..."
sudo apt-get clean
sudo apt-get autoremove -y

# Check disk space
echo ""
echo "📊 Current disk usage:"
df -h

echo ""
echo "✅ Cleanup complete!"

