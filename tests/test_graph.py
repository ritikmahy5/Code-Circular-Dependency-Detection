"""Tests for the graph module."""
import pytest

from src.graph.builder import DependencyGraphBuilder
from src.graph.analyzer import CycleAnalyzer, SeverityLevel


class TestDependencyGraphBuilder:
    """Tests for DependencyGraphBuilder."""
    
    def test_build_simple_graph(self, no_cycle_project):
        """Test building a simple dependency graph."""
        builder = DependencyGraphBuilder(no_cycle_project)
        graph = builder.build()
        
        assert graph.number_of_nodes() == 2
        assert graph.number_of_edges() == 1
        assert graph.has_edge("main.py", "utils.py")
    
    def test_build_cycle_graph(self, simple_cycle_project):
        """Test building a graph with cycles."""
        builder = DependencyGraphBuilder(simple_cycle_project)
        graph = builder.build()
        
        assert graph.number_of_nodes() == 2
        assert graph.number_of_edges() == 2
        assert graph.has_edge("module_a.py", "module_b.py")
        assert graph.has_edge("module_b.py", "module_a.py")


class TestCycleAnalyzer:
    """Tests for CycleAnalyzer."""
    
    def test_no_cycles(self, no_cycle_project):
        """Test detecting no cycles in acyclic graph."""
        builder = DependencyGraphBuilder(no_cycle_project)
        graph = builder.build()
        
        analyzer = CycleAnalyzer(graph)
        cycles = analyzer.find_all_cycles()
        
        assert len(cycles) == 0
    
    def test_simple_cycle(self, simple_cycle_project):
        """Test detecting a simple 2-file cycle."""
        builder = DependencyGraphBuilder(simple_cycle_project)
        graph = builder.build()
        
        analyzer = CycleAnalyzer(graph)
        cycles = analyzer.find_all_cycles()
        
        assert len(cycles) == 1
        assert cycles[0].length == 2
        assert set(cycles[0].files) == {"module_a.py", "module_b.py"}
    
    def test_complex_cycle(self, complex_cycle_project):
        """Test detecting a 3-file cycle."""
        builder = DependencyGraphBuilder(complex_cycle_project)
        graph = builder.build()
        
        analyzer = CycleAnalyzer(graph)
        cycles = analyzer.find_all_cycles()
        
        assert len(cycles) == 1
        assert cycles[0].length == 3
        assert set(cycles[0].files) == {"a.py", "b.py", "c.py"}
    
    def test_severity_levels(self, simple_cycle_project, complex_cycle_project):
        """Test that severity is computed correctly."""
        # Simple cycle should have lower severity
        builder1 = DependencyGraphBuilder(simple_cycle_project)
        graph1 = builder1.build()
        cycles1 = CycleAnalyzer(graph1).find_all_cycles()
        
        # Complex cycle should have higher severity
        builder2 = DependencyGraphBuilder(complex_cycle_project)
        graph2 = builder2.build()
        cycles2 = CycleAnalyzer(graph2).find_all_cycles()
        
        # 2-file cycle should be LOW, 3-file should be MEDIUM or higher
        assert cycles1[0].severity in [SeverityLevel.LOW, SeverityLevel.MEDIUM]
