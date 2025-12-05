"""Severity scoring for detected cycles."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import networkx as nx

from ..graph.analyzer import CycleInfo, SeverityLevel


@dataclass
class SeverityScore:
    """Detailed severity score for a cycle."""
    overall: SeverityLevel
    numeric_score: float  # 0-100
    
    # Component scores
    length_score: float
    coupling_score: float
    centrality_score: float
    import_type_score: float
    
    # Recommendations
    priority_rank: int
    estimated_effort: str  # "low", "medium", "high"
    
    def to_dict(self) -> dict:
        return {
            "overall": self.overall.value,
            "numeric_score": self.numeric_score,
            "length_score": self.length_score,
            "coupling_score": self.coupling_score,
            "centrality_score": self.centrality_score,
            "import_type_score": self.import_type_score,
            "priority_rank": self.priority_rank,
            "estimated_effort": self.estimated_effort,
        }


class SeverityScorer:
    """Computes detailed severity scores for cycles."""
    
    # Weights for different factors
    WEIGHTS = {
        "length": 0.3,
        "coupling": 0.2,
        "centrality": 0.3,
        "import_type": 0.2,
    }
    
    def __init__(self, graph: nx.DiGraph):
        self.graph = graph
        self.total_files = graph.number_of_nodes()
    
    def score_cycle(self, cycle: CycleInfo, rank: int = 0) -> SeverityScore:
        """Compute detailed severity score for a cycle."""
        
        # Length score (longer = worse)
        length_score = min(100, (cycle.length / max(5, self.total_files * 0.1)) * 100)
        
        # Coupling score (denser = worse)
        coupling_score = cycle.coupling_density * 100
        
        # Centrality score (more central = worse)
        centrality_score = min(100, cycle.centrality_score * 200)
        
        # Import type score (type-checking/local = better)
        if cycle.has_type_checking_only:
            import_type_score = 20
        elif cycle.has_local_imports:
            import_type_score = 50
        else:
            import_type_score = 100
        
        # Weighted average
        numeric_score = (
            self.WEIGHTS["length"] * length_score +
            self.WEIGHTS["coupling"] * coupling_score +
            self.WEIGHTS["centrality"] * centrality_score +
            self.WEIGHTS["import_type"] * import_type_score
        )
        
        # Determine overall severity
        if numeric_score >= 75:
            overall = SeverityLevel.CRITICAL
        elif numeric_score >= 50:
            overall = SeverityLevel.HIGH
        elif numeric_score >= 25:
            overall = SeverityLevel.MEDIUM
        else:
            overall = SeverityLevel.LOW
        
        # Estimate effort
        if cycle.length <= 2 and (cycle.has_type_checking_only or cycle.has_local_imports):
            effort = "low"
        elif cycle.length <= 3:
            effort = "medium"
        else:
            effort = "high"
        
        return SeverityScore(
            overall=overall,
            numeric_score=round(numeric_score, 2),
            length_score=round(length_score, 2),
            coupling_score=round(coupling_score, 2),
            centrality_score=round(centrality_score, 2),
            import_type_score=round(import_type_score, 2),
            priority_rank=rank,
            estimated_effort=effort,
        )
    
    def score_all_cycles(self, cycles: list[CycleInfo]) -> dict[int, SeverityScore]:
        """Score all cycles and return mapping by cycle_id."""
        # Sort by preliminary score to assign ranks
        scored = []
        for cycle in cycles:
            score = self.score_cycle(cycle)
            scored.append((cycle.cycle_id, score))
        
        # Sort by numeric score descending
        scored.sort(key=lambda x: -x[1].numeric_score)
        
        # Assign ranks
        result = {}
        for rank, (cycle_id, score) in enumerate(scored, 1):
            score.priority_rank = rank
            result[cycle_id] = score
        
        return result
