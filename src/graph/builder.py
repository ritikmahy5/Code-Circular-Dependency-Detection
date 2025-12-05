"""Dependency graph construction from parsed imports."""
import networkx as nx
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from ..parser import ImportExtractor, ModuleResolver


@dataclass 
class DependencyEdge:
    """An edge in the dependency graph."""
    source: str           # Importing file
    target: str           # Imported file
    import_type: str      # 'import', 'from', 'relative'
    is_type_checking: bool = False
    is_local: bool = False
    line_number: int = 0
    names: list[str] = field(default_factory=list)


class DependencyGraphBuilder:
    """Builds a directed dependency graph from Python files."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.resolver = ModuleResolver(project_root)
        self.graph = nx.DiGraph()
        self.edges: list[DependencyEdge] = []
    
    def build(self) -> nx.DiGraph:
        """Build the complete dependency graph."""
        python_files = self.resolver.get_all_python_files()
        
        # Add all files as nodes
        for file_path in python_files:
            rel_path = str(file_path.relative_to(self.project_root))
            self.graph.add_node(rel_path, path=str(file_path))
        
        # Extract imports and add edges
        for file_path in python_files:
            self._process_file(file_path)
        
        return self.graph
    
    def _process_file(self, file_path: Path) -> None:
        """Process a single file and add its import edges."""
        rel_source = str(file_path.relative_to(self.project_root))
        
        extractor = ImportExtractor(file_path, self.project_root)
        imports = extractor.extract()
        
        for imp in imports:
            resolved = self.resolver.resolve(
                imp.module,
                file_path,
                level=imp.level
            )
            
            if resolved.is_internal and resolved.resolved_path:
                rel_target = str(resolved.resolved_path.relative_to(self.project_root))
                
                edge = DependencyEdge(
                    source=rel_source,
                    target=rel_target,
                    import_type='relative' if imp.is_relative else 'from' if imp.names else 'import',
                    is_type_checking=imp.is_type_checking,
                    is_local=imp.is_local,
                    line_number=imp.line_number,
                    names=imp.names,
                )
                self.edges.append(edge)
                
                # Add edge to graph with metadata
                self.graph.add_edge(
                    rel_source, 
                    rel_target,
                    type_checking=imp.is_type_checking,
                    local=imp.is_local,
                    line=imp.line_number,
                )
    
    def get_edge_info(self, source: str, target: str) -> Optional[DependencyEdge]:
        """Get detailed info about an edge."""
        for edge in self.edges:
            if edge.source == source and edge.target == target:
                return edge
        return None
