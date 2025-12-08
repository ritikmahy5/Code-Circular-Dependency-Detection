#!/bin/bash
# Clear Python cache files for NLP_Project
# Run this before restarting Streamlit after code changes

echo "🧹 Clearing Python cache..."

# Navigate to project
cd /Users/ritik/Desktop/NLP_Project

# Remove all __pycache__ directories
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null

# Remove all .pyc files
find . -type f -name "*.pyc" -delete 2>/dev/null

# Remove .pytest_cache if exists
rm -rf .pytest_cache 2>/dev/null

echo "✅ Cache cleared!"
echo ""
echo "Now restart Streamlit with:"
echo "  streamlit run src/web/streamlit_app.py"
