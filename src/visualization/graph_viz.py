"""Dependency graph visualization using Pyvis."""
from pathlib import Path
from typing import Optional
import networkx as nx
import json

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
            # Also add the closing edge
            if cycle.chain:
                self._cycle_edges.add((cycle.chain[-1], cycle.chain[0]))
    
    def generate_html(
        self, 
        output_path: Path,
        height: str = "750px",
        width: str = "100%",
        notebook: bool = False,
    ) -> Path:
        """Generate interactive HTML visualization with embedded CDN libraries."""
        
        # Build nodes data
        nodes = []
        for node in self.graph.nodes():
            color = self._get_node_color(node)
            title = self._get_node_tooltip(node)
            
            # Calculate node size based on degree centrality
            degree = self.graph.degree(node)
            node_size = 20 + (degree * 3)
            if node in self._cycle_nodes:
                node_size += 10
            
            nodes.append({
                "id": node,
                "label": self._get_short_name(node),
                "title": title,
                "color": color,
                "size": node_size,
                "borderWidth": 3 if node in self._cycle_nodes else 2,
                "font": {"size": 12}
            })
        
        # Build edges data
        edges = []
        for source, target in self.graph.edges():
            is_cycle_edge = (source, target) in self._cycle_edges
            color = self.COLORS["edge_cycle"] if is_cycle_edge else self.COLORS["edge_normal"]
            width = 3 if is_cycle_edge else 1
            
            edge_data = self.graph.edges[source, target]
            title = f"Line {edge_data.get('line', '?')}"
            if edge_data.get('type_checking'):
                title += " (TYPE_CHECKING)"
            if edge_data.get('local'):
                title += " (local import)"
            
            edges.append({
                "from": source,
                "to": target,
                "color": {"color": color},
                "width": width,
                "title": title,
                "arrows": {"to": {"enabled": True, "scaleFactor": 0.5}}
            })
        
        # Generate self-contained HTML with CDN
        html_content = self._generate_standalone_html(nodes, edges, height, width)
        
        # Save
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return output_path
    
    def _generate_standalone_html(self, nodes: list, edges: list, height: str, width: str) -> str:
        """Generate self-contained HTML with vis.js from CDN."""
        
        nodes_json = json.dumps(nodes)
        edges_json = json.dumps(edges)
        
        html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Dependency Graph Visualization</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style type="text/css">
        html, body {{
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
            font-family: Arial, sans-serif;
        }}
        #mynetwork {{
            width: {width};
            height: {height};
            border: 1px solid #ddd;
            background-color: #ffffff;
        }}
        #legend {{
            position: absolute;
            bottom: 10px;
            left: 10px;
            background: rgba(255, 255, 255, 0.95);
            border: 2px solid #333;
            border-radius: 8px;
            padding: 12px;
            font-size: 12px;
            z-index: 1000;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }}
        #legend h4 {{
            margin: 0 0 8px 0;
            font-size: 14px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            margin: 4px 0;
        }}
        .legend-color {{
            width: 16px;
            height: 16px;
            border-radius: 3px;
            margin-right: 8px;
            border: 1px solid #333;
        }}
        .legend-line {{
            width: 30px;
            height: 3px;
            margin-right: 8px;
        }}
        #stats {{
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(255, 255, 255, 0.95);
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 12px;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div id="mynetwork"></div>
    
    <div id="legend">
        <h4>📋 Color Legend</h4>
        <div><strong>Node Colors:</strong></div>
        <div class="legend-item">
            <div class="legend-color" style="background-color: #97C2FC;"></div>
            <span>Normal (no cycle)</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background-color: #90EE90;"></div>
            <span>Low severity</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background-color: #FFD700;"></div>
            <span>Medium severity</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background-color: #FFA500;"></div>
            <span>High severity</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background-color: #FF4500;"></div>
            <span>Critical severity</span>
        </div>
        <div style="margin-top: 8px;"><strong>Edge Colors:</strong></div>
        <div class="legend-item">
            <div class="legend-line" style="background-color: #848484;"></div>
            <span>Normal dependency</span>
        </div>
        <div class="legend-item">
            <div class="legend-line" style="background-color: #FF0000;"></div>
            <span>Circular dependency</span>
        </div>
    </div>
    
    <div id="stats">
        <strong>📊 Graph Stats</strong><br>
        Nodes: {len(nodes)}<br>
        Edges: {len(edges)}<br>
        Cycles: {len(self._cycles)}
    </div>

    <script type="text/javascript">
        // Create nodes and edges
        var nodes = new vis.DataSet({nodes_json});
        var edges = new vis.DataSet({edges_json});

        // Create network
        var container = document.getElementById('mynetwork');
        var data = {{
            nodes: nodes,
            edges: edges
        }};
        
        var options = {{
            physics: {{
                enabled: true,
                solver: 'forceAtlas2Based',
                forceAtlas2Based: {{
                    gravitationalConstant: -100,
                    centralGravity: 0.01,
                    springLength: 200,
                    springConstant: 0.08,
                    damping: 0.4,
                    avoidOverlap: 0.5
                }},
                stabilization: {{
                    enabled: true,
                    iterations: 200,
                    updateInterval: 25
                }}
            }},
            nodes: {{
                shape: 'dot',
                font: {{
                    size: 14,
                    face: 'Arial'
                }},
                shadow: true
            }},
            edges: {{
                smooth: {{
                    enabled: true,
                    type: 'dynamic'
                }},
                shadow: true
            }},
            interaction: {{
                hover: true,
                tooltipDelay: 100,
                navigationButtons: true,
                keyboard: true,
                zoomView: true,
                dragView: true
            }}
        }};

        var network = new vis.Network(container, data, options);
        
        // Stop physics after stabilization
        network.on("stabilizationIterationsDone", function () {{
            network.setOptions({{ physics: {{ enabled: false }} }});
        }});
    </script>
</body>
</html>'''
        
        return html
    
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
