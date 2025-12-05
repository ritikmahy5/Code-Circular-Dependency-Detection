"""Structure-aware code chunking using AST."""
import ast
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class ChunkType(Enum):
    """Types of code chunks."""
    MODULE = "module"
    CLASS = "class"
    METHOD = "method"
    FUNCTION = "function"
    IMPORT_BLOCK = "import_block"
    TOP_LEVEL = "top_level"


@dataclass
class CodeChunk:
    """A semantically complete code unit with full context."""
    
    # Identity
    chunk_id: str
    chunk_type: ChunkType
    
    # Location
    file_path: str
    start_line: int
    end_line: int
    
    # Content
    source_code: str
    
    # Hierarchy
    parent_chunk_id: Optional[str] = None
    children_ids: list[str] = field(default_factory=list)
    
    # Semantic metadata
    name: str = ""
    docstring: Optional[str] = None
    signature: Optional[str] = None
    
    # Dependency info
    imports_from: list[str] = field(default_factory=list)
    imported_by: list[str] = field(default_factory=list)
    
    # Context for embedding
    context_header: str = ""
    
    def to_embedding_text(self) -> str:
        """Generate text for embedding."""
        parts = [self.context_header]
        if self.docstring:
            parts.append(f"Docstring: {self.docstring}")
        if self.signature:
            parts.append(f"Signature: {self.signature}")
        parts.append(self.source_code)
        return "\n".join(parts)


class StructureAwareChunker:
    """Chunks Python code by AST structure, preserving semantic integrity."""
    
    def __init__(self, max_chunk_lines: int = 100):
        self.max_chunk_lines = max_chunk_lines
        self.chunks: list[CodeChunk] = []
        self._lines: list[str] = []
        self._file_path: str = ""
        self._imports: list[str] = []
    
    def chunk_file(self, file_path: Path) -> list[CodeChunk]:
        """Chunk a Python file into semantic units."""
        self.chunks = []
        self._file_path = str(file_path)
        
        try:
            source = file_path.read_text(encoding='utf-8')
            self._lines = source.splitlines()
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, Exception) as e:
            print(f"Warning: Could not parse {file_path}: {e}")
            return []
        
        # Extract imports first
        self._imports = self._extract_imports(tree)
        
        # Create import block chunk
        self._chunk_imports(tree)
        
        # Process top-level nodes
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                self._chunk_class(node)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._chunk_function(node, parent=None)
            elif not isinstance(node, (ast.Import, ast.ImportFrom)):
                # Top-level statements
                if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
                    self._chunk_top_level(node)
        
        return self.chunks
    
    def _chunk_imports(self, tree: ast.Module) -> None:
        """Create a chunk for all import statements."""
        import_nodes = [
            node for node in ast.iter_child_nodes(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        
        if not import_nodes:
            return
        
        start = min(n.lineno for n in import_nodes)
        end = max(n.end_lineno or n.lineno for n in import_nodes)
        
        self.chunks.append(CodeChunk(
            chunk_id=f"{self._file_path}::imports",
            chunk_type=ChunkType.IMPORT_BLOCK,
            file_path=self._file_path,
            start_line=start,
            end_line=end,
            source_code=self._get_source(start, end),
            name="imports",
            context_header=f"Import statements in {self._file_path}",
            imports_from=self._imports,
        ))
    
    def _chunk_class(self, node: ast.ClassDef) -> str:
        """Chunk a class definition and its methods."""
        class_id = f"{self._file_path}::{node.name}"
        
        # Get class header (definition + docstring + class attributes)
        class_header = self._extract_class_header(node)
        
        class_chunk = CodeChunk(
            chunk_id=class_id,
            chunk_type=ChunkType.CLASS,
            file_path=self._file_path,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            source_code=class_header,
            name=node.name,
            docstring=ast.get_docstring(node),
            imports_from=self._imports,
            context_header=f"Class `{node.name}` in {self._file_path}",
        )
        self.chunks.append(class_chunk)
        
        # Chunk each method
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_id = self._chunk_function(
                    item, 
                    parent=class_chunk,
                    context_prefix=f"In class `{node.name}`"
                )
                class_chunk.children_ids.append(method_id)
        
        return class_id
    
    def _chunk_function(
        self, 
        node: ast.FunctionDef, 
        parent: Optional[CodeChunk],
        context_prefix: str = ""
    ) -> str:
        """Chunk a function or method."""
        if parent:
            func_id = f"{self._file_path}::{parent.name}.{node.name}"
            chunk_type = ChunkType.METHOD
        else:
            func_id = f"{self._file_path}::{node.name}"
            chunk_type = ChunkType.FUNCTION
        
        func_source = self._get_source(node.lineno, node.end_lineno or node.lineno)
        signature = self._extract_signature(node)
        
        if context_prefix:
            context = f"{context_prefix}, method `{node.name}`"
        else:
            context = f"Function `{node.name}` in {self._file_path}"
        
        chunk = CodeChunk(
            chunk_id=func_id,
            chunk_type=chunk_type,
            file_path=self._file_path,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            source_code=func_source,
            parent_chunk_id=parent.chunk_id if parent else None,
            name=node.name,
            docstring=ast.get_docstring(node),
            signature=signature,
            imports_from=self._imports,
            context_header=context,
        )
        self.chunks.append(chunk)
        
        return func_id
    
    def _chunk_top_level(self, node: ast.AST) -> None:
        """Chunk top-level statements."""
        if not hasattr(node, 'lineno') or not hasattr(node, 'end_lineno'):
            return
        
        source = self._get_source(node.lineno, node.end_lineno or node.lineno)
        chunk_id = f"{self._file_path}::top_level_{node.lineno}"
        
        self.chunks.append(CodeChunk(
            chunk_id=chunk_id,
            chunk_type=ChunkType.TOP_LEVEL,
            file_path=self._file_path,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            source_code=source,
            context_header=f"Top-level code in {self._file_path}",
        ))
    
    def _extract_imports(self, tree: ast.Module) -> list[str]:
        """Extract all imported module names."""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return imports
    
    def _extract_class_header(self, node: ast.ClassDef) -> str:
        """Extract class definition, docstring, and class-level attributes."""
        lines = []
        
        # Class definition line
        lines.append(self._get_source(node.lineno, node.lineno))
        
        # Docstring
        if ast.get_docstring(node):
            # Find docstring node
            if node.body and isinstance(node.body[0], ast.Expr):
                if isinstance(node.body[0].value, ast.Constant):
                    ds_node = node.body[0]
                    lines.append(self._get_source(ds_node.lineno, ds_node.end_lineno or ds_node.lineno))
        
        # Class attributes (before first method)
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                break
            if isinstance(item, (ast.Assign, ast.AnnAssign)):
                lines.append(self._get_source(item.lineno, item.end_lineno or item.lineno))
        
        return "\n".join(lines)
    
    def _extract_signature(self, node: ast.FunctionDef) -> str:
        """Extract function signature."""
        args = []
        
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                try:
                    arg_str += f": {ast.unparse(arg.annotation)}"
                except:
                    pass
            args.append(arg_str)
        
        returns = ""
        if node.returns:
            try:
                returns = f" -> {ast.unparse(node.returns)}"
            except:
                pass
        
        async_prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
        return f"{async_prefix}def {node.name}({', '.join(args)}){returns}"
    
    def _get_source(self, start: int, end: int) -> str:
        """Get source code between line numbers (1-indexed)."""
        return "\n".join(self._lines[start - 1:end])
