"""Module path resolution for import statements."""
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class ResolvedImport:
    """A resolved import with absolute path."""
    original_module: str
    resolved_path: Optional[Path]
    is_internal: bool
    is_package: bool = False


class ModuleResolver:
    """Resolves import statements to file paths."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self._module_cache: dict[str, ResolvedImport] = {}
    
    def resolve(self, module: str, from_file: Path, level: int = 0) -> ResolvedImport:
        """Resolve a module name to its file path."""
        cache_key = f"{from_file}:{module}:{level}"
        if cache_key in self._module_cache:
            return self._module_cache[cache_key]
        
        if level > 0:
            # Relative import
            resolved = self._resolve_relative(module, from_file, level)
        else:
            # Absolute import
            resolved = self._resolve_absolute(module)
        
        self._module_cache[cache_key] = resolved
        return resolved
    
    def _resolve_relative(self, module: str, from_file: Path, level: int) -> ResolvedImport:
        """Resolve a relative import."""
        # Go up 'level' directories from the file
        base_dir = from_file.parent
        for _ in range(level - 1):
            base_dir = base_dir.parent
        
        if module:
            # from ..foo import bar
            target = base_dir / module.replace('.', '/')
        else:
            # from .. import bar
            target = base_dir
        
        return self._find_module(module or str(base_dir.relative_to(self.project_root)), target)
    
    def _resolve_absolute(self, module: str) -> ResolvedImport:
        """Resolve an absolute import."""
        module_path = module.replace('.', '/')
        target = self.project_root / module_path
        return self._find_module(module, target)
    
    def _find_module(self, module: str, target: Path) -> ResolvedImport:
        """Find the actual file for a module path."""
        # Check for package (directory with __init__.py)
        init_file = target / "__init__.py"
        if init_file.exists():
            return ResolvedImport(
                original_module=module,
                resolved_path=init_file,
                is_internal=self._is_internal(init_file),
                is_package=True,
            )
        
        # Check for module file
        module_file = target.with_suffix('.py')
        if module_file.exists():
            return ResolvedImport(
                original_module=module,
                resolved_path=module_file,
                is_internal=self._is_internal(module_file),
                is_package=False,
            )
        
        # Not found (external or doesn't exist)
        return ResolvedImport(
            original_module=module,
            resolved_path=None,
            is_internal=False,
        )
    
    def _is_internal(self, path: Path) -> bool:
        """Check if a path is within the project."""
        try:
            path.resolve().relative_to(self.project_root)
            return True
        except ValueError:
            return False
    
    def get_all_python_files(self) -> list[Path]:
        """Get all Python files in the project."""
        return list(self.project_root.rglob("*.py"))
