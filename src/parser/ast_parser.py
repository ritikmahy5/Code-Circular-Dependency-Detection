"""AST-based import extraction from Python files."""
import ast
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import sys


@dataclass
class ImportInfo:
    """Information about a single import statement."""
    module: str                          # The module being imported
    names: list[str] = field(default_factory=list)  # Specific names imported
    alias: Optional[str] = None          # Import alias (as ...)
    is_relative: bool = False            # from . import or from .. import
    level: int = 0                       # Relative import level
    line_number: int = 0                 # Line in source file
    is_type_checking: bool = False       # Inside TYPE_CHECKING block
    is_local: bool = False               # Inside function/method


class ImportExtractor(ast.NodeVisitor):
    """Extract all imports from a Python file using AST."""
    
    # Standard library modules (Python 3.10+)
    STDLIB_MODULES: set[str] = set(sys.stdlib_module_names) if hasattr(sys, 'stdlib_module_names') else {
        'abc', 'asyncio', 'collections', 'contextlib', 'dataclasses', 'datetime',
        'enum', 'functools', 'io', 'itertools', 'json', 'logging', 'math', 'os',
        'pathlib', 'pickle', 're', 'shutil', 'socket', 'sqlite3', 'string',
        'subprocess', 'sys', 'tempfile', 'threading', 'time', 'typing', 'unittest',
        'urllib', 'uuid', 'warnings', 'weakref', 'xml', 'zipfile',
    }
    
    def __init__(self, file_path: Path, package_root: Optional[Path] = None):
        self.file_path = file_path
        self.package_root = package_root or file_path.parent
        self.imports: list[ImportInfo] = []
        self._in_type_checking = False
        self._in_function = False
        self._current_class = None
    
    def extract(self) -> list[ImportInfo]:
        """Parse file and extract all imports."""
        try:
            source = self.file_path.read_text(encoding='utf-8')
            tree = ast.parse(source, filename=str(self.file_path))
            self.visit(tree)
        except SyntaxError as e:
            print(f"Warning: Syntax error in {self.file_path}: {e}")
        except Exception as e:
            print(f"Warning: Could not parse {self.file_path}: {e}")
        return self.imports
    
    def visit_If(self, node: ast.If):
        """Check for TYPE_CHECKING blocks."""
        if self._is_type_checking_block(node):
            old_state = self._in_type_checking
            self._in_type_checking = True
            self.generic_visit(node)
            self._in_type_checking = old_state
        else:
            self.generic_visit(node)
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Track when we're inside a function (local imports)."""
        old_state = self._in_function
        self._in_function = True
        self.generic_visit(node)
        self._in_function = old_state
    
    visit_AsyncFunctionDef = visit_FunctionDef
    
    def visit_ClassDef(self, node: ast.ClassDef):
        """Track current class context."""
        old_class = self._current_class
        self._current_class = node.name
        self.generic_visit(node)
        self._current_class = old_class
    
    def visit_Import(self, node: ast.Import):
        """Handle 'import x' statements."""
        for alias in node.names:
            self.imports.append(ImportInfo(
                module=alias.name,
                alias=alias.asname,
                is_relative=False,
                level=0,
                line_number=node.lineno,
                is_type_checking=self._in_type_checking,
                is_local=self._in_function,
            ))
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Handle 'from x import y' statements."""
        module = node.module or ''
        names = [alias.name for alias in node.names]
        
        self.imports.append(ImportInfo(
            module=module,
            names=names,
            is_relative=node.level > 0,
            level=node.level,
            line_number=node.lineno,
            is_type_checking=self._in_type_checking,
            is_local=self._in_function,
        ))
        self.generic_visit(node)
    
    def _is_type_checking_block(self, node: ast.If) -> bool:
        """Check if this is a TYPE_CHECKING block."""
        test = node.test
        # Handle: if TYPE_CHECKING:
        if isinstance(test, ast.Name) and test.id == 'TYPE_CHECKING':
            return True
        # Handle: if typing.TYPE_CHECKING:
        if isinstance(test, ast.Attribute) and test.attr == 'TYPE_CHECKING':
            return True
        return False
    
    def get_internal_imports(self) -> list[ImportInfo]:
        """Filter to only internal project imports."""
        return [
            imp for imp in self.imports
            if not self._is_external(imp.module)
        ]
    
    def _is_external(self, module: str) -> bool:
        """Check if module is external (stdlib or third-party)."""
        if not module:
            return False
        top_level = module.split('.')[0]
        return top_level in self.STDLIB_MODULES
