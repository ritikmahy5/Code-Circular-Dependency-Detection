"""Dependency graph visualization using Pyvis."""
from pathlib import Path
from typing import Optional
import networkx as nx

from ..graph.analyzer import CycleInfo, SeverityLevel


class DependencyVisualizer:
    """Visualize dependency graphs with cycle highlighting."""
    
    # Color scheme
    COLORS = {
        "normal": "#97C2FC",      # Light blue
        "in_cycle": "#FB7E81",    # Red
        "warning": "#FFFF00",     # Yellow
        "edge_normal": "#848484", # Gray
        "edge_cycle": "#FF0000",  # Red
    }
    
    SEVERITY_COLORS = {
        SeverityLevel.LOW: "#90EE90",       # Light green
        SeverityLevel.MEDIUM: "#FFD700",    # Gold
        SeverityLevel.HIGH: "#FFA500",      # Orange
        SeverityLevel.CRITICAL: "#FF4500",  # Red-orange
    }
    
    def __init__(self, graph: nx.DiGraph):
        self.graph = graph
        self._cycles: list[CycleInfo] = []
        self._cycle_nodes: set[str] = set()
        self._cycle_edges: set[tuple[str, str]] = set()
    
    def set_cycles(self, cycles: list[CycleInfo]) -> None:
        """Set detected cycles for highlighting."""
        self._cycles = cycles
        self._cycle_nodes = set()
        self._cycle_edges = set()
        
        for cycle in cycles:
            self._cycle_nodes.update(cycle.files)
            # Add edges from the chain
            for i in range(len(cycle.chain) - 1):
                self._cycle_edges.add((cycle.chain[i], cycle.chain[i + 1]))
    
    def generate_html(
        self, 
        output_path: Path,
        height: str = "750px",
        width: str = "100%",
        notebook: bool = False,
    ) -> Path:
        """Generate interactive HTML visualization."""
        from pyvis.network import Network
        
        # Create network
        net = Network(
            height=height,
            width=width,
            directed=True,
            notebook=notebook,
            bgcolor="#ffffff",
            font_color="#000000",
        )
        
        # Configure physics
        net.set_options("""
        {
            "physics": {
                "forceAtlas2Based": {
                    "gravitationalConstant": -50,
                    "centralGravity": 0.01,
                    "springLength": 200,
                    "springConstant": 0.08
                },
                "maxVelocity": 50,
                "solver": "forceAtlas2Based",
                "timestep": 0.35,
                "stabilization": {"iterations": 150}
            },
            "edges": {
                "arrows": {"to": {"enabled": true, "scaleFactor": 0.5}},
                "smooth": {"type": "curvedCW", "roundness": 0.2}
            },
            "interaction": {
                "hover": true,
                "tooltipDelay": 200
            }
        }
        """)
        
        # Add nodes
        for node in self.graph.nodes():
            color = self._get_node_color(node)
            title = self._get_node_tooltip(node)
            
            net.add_node(
                node,
                label=self._get_short_name(node),
                title=title,
                color=color,
                size=25 if node in self._cycle_nodes else 20,
            )
        
        # Add edges
        for source, target in self.graph.edges():
            color = self.COLORS["edge_cycle"] if (source, target) in self._cycle_edges else self.COLORS["edge_normal"]
            width = 3 if (source, target) in self._cycle_edges else 1
            
            edge_data = self.graph.edges[source, target]
            title = f"Line {edge_data.get('line', '?')}"
            if edge_data.get('type_checking'):
                title += " (TYPE_CHECKING)"
            if edge_data.get('local'):
                title += " (local import)"
            
            net.add_edge(
                source, 
                target,
                color=color,
                width=width,
                title=title,
            )
        
        # Save
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        net.save_graph(str(output_path))
        
        return output_path
    
    def _get_node_color(self, node: str) -> str:
        """Get color for a node based on cycle membership."""
        if node not in self._cycle_nodes:
            return self.COLORS["normal"]
        
        # Find most severe cycle this node is in
        max_severity = SeverityLevel.LOW
        for cycle in self._cycles:
            if node in cycle.files:
                if list(SeverityLevel).index(cycle.severity) > list(SeverityLevel).index(max_severity):
                    max_severity = cycle.severity
        
        return self.SEVERITY_COLORS.get(max_severity, self.COLORS["in_cycle"])
    
    def _get_node_tooltip(self, node: str) -> str:
        """Generate tooltip for a node."""
        lines = [f"<b>{node}</b>"]
        
        # Incoming/outgoing counts
        in_degree = self.graph.in_degree(node)
        out_degree = self.graph.out_degree(node)
        lines.append(f"Imports: {out_degree} | Imported by: {in_degree}")
        
        # Cycle membership
        node_cycles = [c for c in self._cycles if node in c.files]
        if node_cycles:
            lines.append(f"<br><b>In {len(node_cycles)} cycle(s):</b>")
            for cycle in node_cycles[:3]:  # Show max 3
                lines.append(f"- Cycle {cycle.cycle_id} ({cycle.severity.value})")
        
        return "<br>".join(lines)
    
    def _get_short_name(self, path: str) -> str:
        """Get a short display name for a file path."""
        parts = path.replace("\\", "/").split("/")
        if len(parts) <= 2:
            return path
        return f".../{'/'.join(parts[-2:])}"
    
    def generate_cycle_subgraph(
        self,
        cycle: CycleInfo,
        output_path: Path,
    ) -> Path:
        """Generate visualization for a specific cycle."""
        subgraph = self.graph.subgraph(cycle.files).copy()
        
        viz = DependencyVisualizer(subgraph)
        viz.set_cycles([cycle])
        
        return viz.generate_html(output_path)
