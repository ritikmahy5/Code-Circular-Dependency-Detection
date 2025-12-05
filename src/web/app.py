"""Web dashboard for Circular Dependency Detective."""
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from pathlib import Path
import tempfile
import shutil

from ..graph.builder import DependencyGraphBuilder
from ..graph.analyzer import CycleAnalyzer
from ..visualization.graph_viz import DependencyVisualizer

app = FastAPI(title="Circular Dependency Detective")

@app.post("/analyze")
async def analyze_project(file: UploadFile = File(...)):
    """Analyze an uploaded Python project."""
    # Implementation here
    pass

@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <html>
        <head><title>Circular Dependency Detective</title></head>
        <body>
            <h1>Upload a Python project to analyze</h1>
            <form action="/analyze" method="post" enctype="multipart/form-data">
                <input type="file" name="file" accept=".zip">
                <button type="submit">Analyze</button>
            </form>
        </body>
    </html>
    """
