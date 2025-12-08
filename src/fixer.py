"""Automatic code fix generation for circular dependencies."""
import ast
import asyncio
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .graph.analyzer import CycleInfo
from .llm.factory import get_llm


class FixStrategy(Enum):
    LAZY_IMPORT = "lazy_import"
    TYPE_CHECKING = "type_checking"
    EXTRACT_INTERFACE = "extract_interface"
    MERGE_MODULES = "merge_modules"


@dataclass
class CodeFix:
    """A proposed code fix."""
    file_path: str
    original_code: str
    fixed_code: str
    strategy: FixStrategy
    description: str
    line_start: int
    line_end: int


LAZY_IMPORT_PROMPT = """Convert this top-level import to a lazy import inside the function that uses it.

Original file content:
```python
{file_content}
```

The import on line {line_number} (`{import_statement}`) causes a circular dependency.
Move this import inside the function(s) that actually use it.

Return ONLY the complete fixed file content, no explanations:"""


TYPE_CHECKING_PROMPT = """Convert this import to a TYPE_CHECKING guarded import.

Original file content:
```python
{file_content}
```

The import on line {line_number} (`{import_statement}`) is only used for type hints.
Wrap it in a TYPE_CHECKING block and use string annotations.

Return ONLY the complete fixed file content, no explanations:"""


class AutoFixer:
    """Generates automatic fixes for circular dependencies."""
    
    def __init__(self):
        self.llm = get_llm()
    
    def _resolve_file_path(self, edge_from: str, project_path: Path) -> Optional[Path]:
        """Resolve file path from edge data, trying multiple strategies."""
        # Strategy 1: Direct path join
        direct_path = project_path / edge_from
        if direct_path.exists():
            return direct_path
        
        # Strategy 2: edge_from might be absolute or have leading parts to strip
        edge_path = Path(edge_from)
        if edge_path.exists():
            return edge_path
        
        # Strategy 3: Search for the file by name
        file_name = edge_path.name
        for found_file in project_path.rglob(file_name):
            # Check if the path ends with what we're looking for
            if str(found_file).endswith(edge_from) or edge_from.endswith(str(found_file.relative_to(project_path))):
                return found_file
        
        # Strategy 4: Try matching just the last few path components
        parts = edge_from.replace("\\", "/").split("/")
        for i in range(len(parts)):
            partial = "/".join(parts[i:])
            for found_file in project_path.rglob(parts[-1]):
                if str(found_file).replace("\\", "/").endswith(partial):
                    return found_file
        
        return None
    
    async def generate_fix(
        self, 
        cycle: CycleInfo, 
        project_path: Path,
        strategy: FixStrategy = FixStrategy.LAZY_IMPORT
    ) -> list[CodeFix]:
        """Generate fixes for a cycle."""
        fixes = []
        
        if not cycle.edge_details:
            return fixes
        
        for edge in cycle.edge_details:
            edge_from = edge.get('from', '')
            if not edge_from:
                continue
            
            # Try to resolve the file path
            file_path = self._resolve_file_path(edge_from, project_path)
            
            if file_path is None or not file_path.exists():
                # Can't find file, skip this edge
                continue
            
            try:
                content = file_path.read_text(encoding='utf-8')
            except Exception:
                continue
            
            line_num = edge.get('line', 0)
            
            # Get the import statement
            lines = content.splitlines()
            if not (0 < line_num <= len(lines)):
                continue
            
            import_stmt = lines[line_num - 1].strip()
            
            # Skip if not an import statement
            if not (import_stmt.startswith('import ') or import_stmt.startswith('from ')):
                continue
            
            # Choose strategy based on import type
            if edge.get('type_checking'):
                # Already TYPE_CHECKING, suggest lazy import
                actual_strategy = FixStrategy.LAZY_IMPORT
            elif edge.get('local'):
                # Already local, skip
                continue
            else:
                actual_strategy = strategy
            
            # Generate fix using LLM
            if actual_strategy == FixStrategy.LAZY_IMPORT:
                prompt = LAZY_IMPORT_PROMPT.format(
                    file_content=content[:5000],  # Limit content size
                    line_number=line_num,
                    import_statement=import_stmt
                )
            elif actual_strategy == FixStrategy.TYPE_CHECKING:
                prompt = TYPE_CHECKING_PROMPT.format(
                    file_content=content[:5000],
                    line_number=line_num,
                    import_statement=import_stmt
                )
            else:
                continue
            
            try:
                response = await self.llm.generate(prompt)
                fixed_code = response.content.strip()
                
                # Clean up markdown code blocks if present
                if fixed_code.startswith("```python"):
                    fixed_code = fixed_code[9:]
                if fixed_code.startswith("```"):
                    fixed_code = fixed_code[3:]
                if fixed_code.endswith("```"):
                    fixed_code = fixed_code[:-3]
                
                fixes.append(CodeFix(
                    file_path=str(file_path),
                    original_code=content,
                    fixed_code=fixed_code.strip(),
                    strategy=actual_strategy,
                    description=f"Convert `{import_stmt}` to {actual_strategy.value}",
                    line_start=line_num,
                    line_end=line_num
                ))
            except Exception as e:
                # LLM call failed, skip this fix
                print(f"LLM error generating fix: {e}")
                continue
        
        return fixes
    
    def generate_fix_sync(
        self, 
        cycle: CycleInfo, 
        project_path: Path,
        strategy: FixStrategy = FixStrategy.LAZY_IMPORT
    ) -> list[CodeFix]:
        """Synchronous version of generate_fix."""
        return asyncio.run(self.generate_fix(cycle, project_path, strategy))
    
    def apply_fixes(self, fixes: list[CodeFix], dry_run: bool = True) -> dict:
        """Apply fixes to files."""
        results = {"applied": [], "skipped": [], "errors": []}
        
        for fix in fixes:
            try:
                if dry_run:
                    results["skipped"].append({
                        "file": fix.file_path,
                        "reason": "dry_run",
                        "diff": self._generate_diff(fix)
                    })
                else:
                    Path(fix.file_path).write_text(fix.fixed_code)
                    results["applied"].append(fix.file_path)
            except Exception as e:
                results["errors"].append({
                    "file": fix.file_path,
                    "error": str(e)
                })
        
        return results
    
    def _generate_diff(self, fix: CodeFix) -> str:
        """Generate a unified diff."""
        import difflib
        
        original_lines = fix.original_code.splitlines(keepends=True)
        fixed_lines = fix.fixed_code.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            original_lines,
            fixed_lines,
            fromfile=f"a/{Path(fix.file_path).name}",
            tofile=f"b/{Path(fix.file_path).name}"
        )
        
        return ''.join(diff)
