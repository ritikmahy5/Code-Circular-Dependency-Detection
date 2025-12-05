"""Cycle detection using Tarjan's Strongly Connected Components."""
import networkx as nx
from dataclasses import dataclass, field
from typing import Iterator
from enum import Enum


class SeverityLevel(Enum):
    """Severity levels for cycles."""
    LOW = "low"           # 2-file cycle
    MEDIUM = "medium"     # 3-4 file cycle
    HIGH = "high"         # 5+ file cycle
    CRITICAL = "critical" # Core modules affected


@dataclass
class CycleInfo:
    """Information about a detected cycle."""
    cycle_id: int
    files: list[str]
    chain: list[str]  # Import chain showing the cycle
    length: int
    severity: SeverityLevel
    
    # Additional metrics
    has_type_checking_only: bool = False  # All imports are TYPE_CHECKING
    has_local_imports: bool = False       # Some imports are function-local
    coupling_density: float = 0.0         # Edges / possible edges
    centrality_score: float = 0.0         # How central are these files
    
    # For explanations
    edge_details: list[dict] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "cycle_id": self.cycle_id,
            "files": self.files,
            "chain": self.chain,
            "length": self.length,
            "severity": self.severity.value,
            "has_type_checking_only": self.has_type_checking_only,
            "has_local_imports": self.has_local_imports,
            "coupling_density": self.coupling_density,
            "centrality_score": self.centrality_score,
        }


class CycleAnalyzer:
    """Detects and analyzes cycles using Tarjan's SCC algorithm."""
    
    def __init__(self, graph: nx.DiGraph):
        self.graph = graph
        self._cycles: list[CycleInfo] = []
        self._centrality: dict[str, float] = {}
    
    def find_all_cycles(self) -> list[CycleInfo]:
        """Find all cycles using Tarjan's SCC algorithm."""
        self._cycles = []
        
        # Compute centrality for scoring
        if len(self.graph) > 0:
            self._centrality = nx.betweenness_centrality(self.graph)
        
        # Find strongly connected components (Tarjan's algorithm)
        sccs = list(nx.strongly_connected_components(self.graph))
        
        cycle_id = 0
        for scc in sccs:
            if len(scc) > 1:
                # This SCC contains a cycle
                cycle_id += 1
                cycle_info = self._analyze_scc(cycle_id, scc)
                self._cycles.append(cycle_info)
        
        # Also find simple 2-node cycles that might be in size-1 SCCs
        for node in self.graph.nodes():
            for successor in self.graph.successors(node):
                if self.graph.has_edge(successor, node):
                    # Direct bidirectional edge
                    if not self._is_in_existing_cycle([node, successor]):
                        cycle_id += 1
                        cycle_info = self._create_simple_cycle(cycle_id, node, successor)
                        self._cycles.append(cycle_info)
        
        # Sort by severity (highest first)
        self._cycles.sort(key=lambda c: (
            -len(SeverityLevel) + list(SeverityLevel).index(c.severity),
            -c.length,
            -c.centrality_score
        ))
        
        return self._cycles
    
    def _analyze_scc(self, cycle_id: int, scc: set[str]) -> CycleInfo:
        """Analyze a strongly connected component."""
        files = sorted(scc)
        
        # Find one representative cycle path through the SCC
        chain = self._find_cycle_chain(scc)
        
        # Compute metrics
        subgraph = self.graph.subgraph(scc)
        possible_edges = len(scc) * (len(scc) - 1)
        actual_edges = subgraph.number_of_edges()
        coupling_density = actual_edges / possible_edges if possible_edges > 0 else 0
        
        centrality_score = sum(self._centrality.get(f, 0) for f in files) / len(files)
        
        # Check import types
        has_type_checking_only = all(
            self.graph.edges[u, v].get('type_checking', False)
            for u, v in subgraph.edges()
        )
        has_local_imports = any(
            self.graph.edges[u, v].get('local', False)
            for u, v in subgraph.edges()
        )
        
        # Determine severity
        severity = self._compute_severity(len(files), centrality_score, has_type_checking_only)
        
        # Collect edge details
        edge_details = []
        for u, v in subgraph.edges():
            edge_details.append({
                'from': u,
                'to': v,
                'line': self.graph.edges[u, v].get('line', 0),
                'type_checking': self.graph.edges[u, v].get('type_checking', False),
                'local': self.graph.edges[u, v].get('local', False),
            })
        
        return CycleInfo(
            cycle_id=cycle_id,
            files=files,
            chain=chain,
            length=len(files),
            severity=severity,
            has_type_checking_only=has_type_checking_only,
            has_local_imports=has_local_imports,
            coupling_density=coupling_density,
            centrality_score=centrality_score,
            edge_details=edge_details,
        )
    
    def _find_cycle_chain(self, scc: set[str]) -> list[str]:
        """Find a cycle path through the SCC."""
        subgraph = self.graph.subgraph(scc)
        try:
            cycle = nx.find_cycle(subgraph)
            chain = [edge[0] for edge in cycle]
            chain.append(chain[0])  # Close the cycle
            return chain
        except nx.NetworkXNoCycle:
            return list(scc) + [list(scc)[0]]
    
    def _create_simple_cycle(self, cycle_id: int, node1: str, node2: str) -> CycleInfo:
        """Create a CycleInfo for a simple 2-node cycle."""
        files = sorted([node1, node2])
        chain = [node1, node2, node1]
        
        centrality_score = (
            self._centrality.get(node1, 0) + self._centrality.get(node2, 0)
        ) / 2
        
        has_type_checking_only = (
            self.graph.edges[node1, node2].get('type_checking', False) and
            self.graph.edges[node2, node1].get('type_checking', False)
        )
        
        severity = self._compute_severity(2, centrality_score, has_type_checking_only)
        
        return CycleInfo(
            cycle_id=cycle_id,
            files=files,
            chain=chain,
            length=2,
            severity=severity,
            has_type_checking_only=has_type_checking_only,
            coupling_density=1.0,
            centrality_score=centrality_score,
        )
    
    def _compute_severity(
        self, 
        length: int, 
        centrality: float,
        type_checking_only: bool
    ) -> SeverityLevel:
        """Compute severity level for a cycle."""
        if type_checking_only:
            return SeverityLevel.LOW
        
        if length >= 5 or centrality > 0.3:
            return SeverityLevel.CRITICAL
        elif length >= 4:
            return SeverityLevel.HIGH
        elif length >= 3:
            return SeverityLevel.MEDIUM
        else:
            return SeverityLevel.LOW
    
    def _is_in_existing_cycle(self, nodes: list[str]) -> bool:
        """Check if nodes are already part of a detected cycle."""
        node_set = set(nodes)
        for cycle in self._cycles:
            if node_set.issubset(set(cycle.files)):
                return True
        return False
    
    def get_cycles_by_severity(self, severity: SeverityLevel) -> list[CycleInfo]:
        """Filter cycles by severity level."""
        return [c for c in self._cycles if c.severity == severity]
    
    def get_cycle_by_id(self, cycle_id: int) -> CycleInfo | None:
        """Get a specific cycle by ID."""
        for cycle in self._cycles:
            if cycle.cycle_id == cycle_id:
                return cycle
        return None
