# 🐳 Quick Start with Docker

## Prerequisites
- [Docker](https://docs.docker.com/get-docker/) installed
- [Docker Compose](https://docs.docker.com/compose/install/) installed

That's ALL you need! No Python, no pip, no Ollama installation required.

## Setup (One-time)
```bash
# Clone the repository
git clone <your-repo-url>
cd circular-dependency-detective

# Start services and download LLM model
./start.sh
```

First run takes 5-10 minutes to download the LLM model (~4GB).

## Usage

### Analyze a Project
```bash
# Copy your project to analyze
cp -r /path/to/your/project ./project_to_analyze

# Run analysis
./run.sh analyze /app/project_to_analyze -v
```

### Generate Visualization
```bash
./run.sh visualize /app/project_to_analyze -o /app/output/graph.html

# Open output/graph.html in your browser
```

### Get AI Explanations
```bash
./run.sh explain /app/project_to_analyze --cycle-id 1
```

### Interactive Chat
```bash
./run.sh chat /app/project_to_analyze
```

## Stop Services
```bash
./stop.sh
```

## Troubleshooting

**"Cannot connect to Docker daemon"**
- Make sure Docker Desktop is running

**"Ollama model not found"**
- Run `./start.sh` again to pull the model

**Slow performance**
- First run downloads ~4GB model
- Subsequent runs are faster
- For GPU acceleration, uncomment GPU section in docker-compose.yml
