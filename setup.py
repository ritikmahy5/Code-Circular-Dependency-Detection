from setuptools import setup, find_packages

setup(
    name="circular-dependency-detective",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "networkx>=3.0",
        "sentence-transformers>=2.2.0",
        "chromadb>=0.4.0",
        "typer[all]>=0.9.0",
        "rich>=13.0.0",
        "pyvis>=0.3.2",
        "httpx>=0.24.0",
        "pyyaml>=6.0",
        "pydantic>=2.0",
    ],
    entry_points={
        "console_scripts": [
            "cdd=src.cli:app",
        ],
    },
    python_requires=">=3.10",
)
