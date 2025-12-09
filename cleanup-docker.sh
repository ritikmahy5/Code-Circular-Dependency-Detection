#!/bin/bash
# Script to clean up Docker and free disk space

echo "🧹 Cleaning up Docker to free disk space..."

# Remove all stopped containers
echo "Removing stopped containers..."
docker container prune -f

# Remove all unused images
echo "Removing unused images..."
docker image prune -a -f

# Remove all unused volumes
echo "Removing unused volumes..."
docker volume prune -f

# Remove build cache
echo "Removing build cache..."
docker builder prune -a -f

# Show disk space
echo ""
echo "📊 Current disk usage:"
df -h

echo ""
echo "✅ Cleanup complete!"

