#!/bin/bash
echo "Starting Circular Dependency Detective..."
docker-compose up -d ollama
echo "Waiting for Ollama..."
sleep 15
docker-compose exec ollama ollama pull codellama:7b
docker-compose build cdd
echo "Ready! Use: ./run.sh <command>"
