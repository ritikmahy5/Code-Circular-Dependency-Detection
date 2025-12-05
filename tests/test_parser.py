"""Tests for the parser module."""
import pytest
from pathlib import Path

from src.parser.ast_parser import ImportExtractor
from src.parser.chunker import StructureAwareChunker, ChunkType


class TestImportExtractor:
    """Tests for ImportExtractor."""
    
    def test_simple_import(self, temp_project):
        """Test extracting simple imports."""
        test_file = temp_project / "test.py"
        test_file.write_text("""
import os
import sys
from pathlib import Path
""")
        
        extractor = ImportExtractor(test_file)
        imports = extractor.extract()
        
        assert len(imports) == 3
        assert imports[0].module == "os"
        assert imports[1].module == "sys"
        assert imports[2].module == "pathlib"
        assert "Path" in imports[2].names
    
    def test_relative_import(self, temp_project):
        """Test extracting relative imports."""
        test_file = temp_project / "test.py"
        test_file.write_text("""
from . import sibling
from ..parent import something
from .submodule import func
""")
        
        extractor = ImportExtractor(test_file)
        imports = extractor.extract()
        
        assert len(imports) == 3
        assert imports[0].is_relative
        assert imports[0].level == 1
        assert imports[1].level == 2
    
    def test_type_checking_import(self, temp_project):
        """Test detecting TYPE_CHECKING imports."""
        test_file = temp_project / "test.py"
        test_file.write_text("""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from other import SomeClass

def func(obj: "SomeClass"):
    pass
""")
        
        extractor = ImportExtractor(test_file)
        imports = extractor.extract()
        
        type_checking_imports = [i for i in imports if i.is_type_checking]
        assert len(type_checking_imports) == 1
        assert type_checking_imports[0].module == "other"


class TestStructureAwareChunker:
    """Tests for StructureAwareChunker."""
    
    def test_chunk_class(self, temp_project):
        """Test chunking a class definition."""
        test_file = temp_project / "test.py"
        test_file.write_text("""
class MyClass:
    """A test class."""
    
    class_attr = 42
    
    def method_one(self):
        return 1
    
    def method_two(self, x: int) -> int:
        return x + 1
""")
        
        chunker = StructureAwareChunker()
        chunks = chunker.chunk_file(test_file)
        
        class_chunks = [c for c in chunks if c.chunk_type == ChunkType.CLASS]
        method_chunks = [c for c in chunks if c.chunk_type == ChunkType.METHOD]
        
        assert len(class_chunks) == 1
        assert class_chunks[0].name == "MyClass"
        assert len(method_chunks) == 2
    
    def test_chunk_preserves_context(self, temp_project):
        """Test that chunks preserve context."""
        test_file = temp_project / "test.py"
        test_file.write_text("""
from typing import List

class Container:
    def get_items(self) -> List[int]:
        return [1, 2, 3]
""")
        
        chunker = StructureAwareChunker()
        chunks = chunker.chunk_file(test_file)
        
        method_chunk = next(c for c in chunks if c.name == "get_items")
        
        assert method_chunk.parent_chunk_id is not None
        assert "Container" in method_chunk.context_header
        assert "List" in method_chunk.imports_from or "typing" in method_chunk.imports_from
