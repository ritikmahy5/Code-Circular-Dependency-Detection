"""Tests for the CLI."""
import pytest
from typer.testing import CliRunner
from pathlib import Path

from src.cli import app

runner = CliRunner()


class TestCLI:
    """Tests for CLI commands."""
    
    def test_analyze_no_cycles(self, no_cycle_project):
        """Test analyze command with no cycles."""
        result = runner.invoke(app, ["analyze", str(no_cycle_project)])
        
        assert result.exit_code == 0
        assert "No circular dependencies" in result.stdout
    
    def test_analyze_with_cycles(self, simple_cycle_project):
        """Test analyze command with cycles."""
        result = runner.invoke(app, ["analyze", str(simple_cycle_project)])
        
        assert result.exit_code == 0
        assert "circular dependency" in result.stdout.lower()
    
    def test_analyze_nonexistent_path(self):
        """Test analyze command with nonexistent path."""
        result = runner.invoke(app, ["analyze", "/nonexistent/path"])
        
        assert result.exit_code == 1
        assert "does not exist" in result.stdout.lower()
    
    def test_visualize(self, simple_cycle_project, temp_project):
        """Test visualize command."""
        output_file = temp_project / "output.html"
        result = runner.invoke(app, [
            "visualize", 
            str(simple_cycle_project),
            "-o", str(output_file)
        ])
        
        assert result.exit_code == 0
        assert output_file.exists()
        
        content = output_file.read_text()
        assert "html" in content.lower()
