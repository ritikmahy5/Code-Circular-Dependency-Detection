"""Pytest configuration and fixtures."""
import pytest
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def temp_project():
    """Create a temporary project directory."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def simple_cycle_project(temp_project):
    """Create a project with a simple 2-file cycle."""
    # module_a.py imports from module_b
    (temp_project / "module_a.py").write_text("""
from module_b import func_b

def func_a():
    return func_b() + 1
""")
    
    # module_b.py imports from module_a
    (temp_project / "module_b.py").write_text("""
from module_a import func_a

def func_b():
    return 42
""")
    
    return temp_project


@pytest.fixture  
def complex_cycle_project(temp_project):
    """Create a project with a 3-file cycle."""
    (temp_project / "a.py").write_text("""
from b import B

class A:
    def __init__(self):
        self.b = B()
""")
    
    (temp_project / "b.py").write_text("""
from c import C

class B:
    def __init__(self):
        self.c = C()
""")
    
    (temp_project / "c.py").write_text("""
from a import A

class C:
    def __init__(self):
        self.a = A()
""")
    
    return temp_project


@pytest.fixture
def no_cycle_project(temp_project):
    """Create a project with no cycles."""
    (temp_project / "main.py").write_text("""
from utils import helper

def main():
    return helper()
""")
    
    (temp_project / "utils.py").write_text("""
def helper():
    return 42
""")
    
    return temp_project
