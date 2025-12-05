# Circular Dependency Detective

A tool that systematically detects circular dependencies in Python codebases using Tarjan's Strongly Connected Components algorithm and provides natural language explanations and refactoring recommendations using RAG-enhanced LLMs.

## Features

- **100% Cycle Detection**: Uses Tarjan's SCC algorithm for guaranteed completeness
- **Structure-Aware Code Chunking**: AST-based chunking preserves semantic integrity
- **Dual Knowledge Base**: Code context + Refactoring patterns
- **Local LLM Support**: Runs entirely on GCP with Ollama
- **Interactive Visualizations**: Pyvis-powered dependency graphs
- **Severity Scoring**: Prioritize fixes by impact

## Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Pull Ollama model (for local LLM)
ollama pull codellama:13b
```

## Quick Start

### Local Development

```bash
# Analyze a Python project
python -m src.cli analyze /path/to/your/project

# Generate visualization
python -m src.cli visualize /path/to/your/project -o report.html

# Get detailed explanations
python -m src.cli explain /path/to/your/project --cycle-id 1
```

### Docker Deployment

```bash
# Start services (Ollama + CDD)
docker-compose up -d

# Run analysis
./run.sh analyze /path/to/project -v

# See DOCKER_INSTRUCTIONS.md for details
```

### GCP Deployment

```bash
# Quick setup (5 minutes)
gcloud compute instances create cdd-vm --machine-type=n1-standard-4 ...

# See QUICKSTART_GCP.md for fast setup
# See GCP_DEPLOYMENT.md for complete guide
```

## Project Structure

```
src/
├── parser/          # AST parsing and import extraction
├── graph/           # Dependency graph and cycle detection
├── scoring/         # Severity metrics
├── knowledge/       # Schemas and pattern definitions
├── rag/             # Retrieval-Augmented Generation
├── llm/             # LLM integrations (Ollama, Claude)
├── explainer/       # Cycle explanation generation
├── visualization/   # Graph visualization
└── cli.py           # Command-line interface
```

## Authors

Karan Kendre, Ritik Mahyavanshi, Atharva Dhumal, Akshay Prajapati

Northeastern University, Khoury College of Computer Science
CS 6120 Natural Language Processing
