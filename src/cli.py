"""Command-line interface for Circular Dependency Detective."""
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

app = typer.Typer(
    name="cdd",
    help="Circular Dependency Detective - Detect and fix circular imports",
)
console = Console()


@app.command()
def analyze(
    project_path: Path = typer.Argument(..., help="Path to Python project"),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help="Output JSON file"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose output"),
):
    """Analyze a Python project for circular dependencies."""
    from .graph.builder import DependencyGraphBuilder
    from .graph.analyzer import CycleAnalyzer
    from .scoring.severity import SeverityScorer
    
    if not project_path.exists():
        console.print(f"[red]Error: Path does not exist: {project_path}[/red]")
        raise typer.Exit(1)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Build graph
        task = progress.add_task("Building dependency graph...", total=None)
        builder = DependencyGraphBuilder(project_path)
        graph = builder.build()
        progress.update(task, completed=True)
        
        console.print(f"[green]✓[/green] Found {graph.number_of_nodes()} files, {graph.number_of_edges()} imports")
        
        # Find cycles
        task = progress.add_task("Detecting cycles...", total=None)
        analyzer = CycleAnalyzer(graph)
        cycles = analyzer.find_all_cycles()
        progress.update(task, completed=True)
    
    if not cycles:
        console.print("[green]✓ No circular dependencies detected![/green]")
        return
    
    # Score cycles
    scorer = SeverityScorer(graph)
    scores = scorer.score_all_cycles(cycles)
    
    # Display results
    console.print(f"\n[red]⚠ Found {len(cycles)} circular dependency cycle(s)[/red]\n")
    
    table = Table(title="Detected Cycles")
    table.add_column("ID", style="cyan")
    table.add_column("Severity", style="magenta")
    table.add_column("Files", style="green")
    table.add_column("Chain")
    table.add_column("Score", justify="right")
    
    for cycle in cycles:
        score = scores[cycle.cycle_id]
        severity_color = {
            "low": "green",
            "medium": "yellow",
            "high": "red",
            "critical": "bold red",
        }.get(cycle.severity.value, "white")
        
        chain_display = " → ".join(cycle.chain[:4])
        if len(cycle.chain) > 4:
            chain_display += " → ..."
        
        table.add_row(
            str(cycle.cycle_id),
            f"[{severity_color}]{cycle.severity.value.upper()}[/{severity_color}]",
            str(cycle.length),
            chain_display,
            f"{score.numeric_score:.1f}",
        )
    
    console.print(table)
    
    if verbose:
        console.print("\n[bold]Cycle Details:[/bold]")
        for cycle in cycles:
            console.print(f"\n[cyan]Cycle {cycle.cycle_id}:[/cyan]")
            for edge in cycle.edge_details:
                flags = []
                if edge.get("type_checking"):
                    flags.append("TYPE_CHECKING")
                if edge.get("local"):
                    flags.append("local")
                flag_str = f" ({', '.join(flags)})" if flags else ""
                console.print(f"  {edge['from']} → {edge['to']} (line {edge.get('line', '?')}){flag_str}")
    
    # Save output
    if output:
        import json
        result = {
            "project": str(project_path),
            "total_files": graph.number_of_nodes(),
            "total_imports": graph.number_of_edges(),
            "cycles": [
                {**cycle.to_dict(), "score": scores[cycle.cycle_id].to_dict()}
                for cycle in cycles
            ],
        }
        output.write_text(json.dumps(result, indent=2))
        console.print(f"\n[green]Results saved to {output}[/green]")


@app.command()
def visualize(
    project_path: Path = typer.Argument(..., help="Path to Python project"),
    output: Path = typer.Option("dependency_graph.html", "-o", "--output", help="Output HTML file"),
):
    """Generate interactive visualization of dependencies."""
    from .graph.builder import DependencyGraphBuilder
    from .graph.analyzer import CycleAnalyzer
    from .visualization.graph_viz import DependencyVisualizer
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Building graph...", total=None)
        builder = DependencyGraphBuilder(project_path)
        graph = builder.build()
        progress.update(task, completed=True)
        
        task = progress.add_task("Finding cycles...", total=None)
        analyzer = CycleAnalyzer(graph)
        cycles = analyzer.find_all_cycles()
        progress.update(task, completed=True)
        
        task = progress.add_task("Generating visualization...", total=None)
        viz = DependencyVisualizer(graph)
        viz.set_cycles(cycles)
        output_path = viz.generate_html(output)
        progress.update(task, completed=True)
    
    console.print(f"[green]✓ Visualization saved to {output_path}[/green]")
    console.print(f"  Open in browser to view interactive graph")


@app.command()
def explain(
    project_path: Path = typer.Argument(..., help="Path to Python project"),
    cycle_id: int = typer.Option(1, "--cycle-id", "-c", help="Cycle ID to explain"),
    patterns_dir: Optional[Path] = typer.Option(None, "--patterns", "-p", help="Path to patterns directory"),
):
    """Generate explanation and refactoring advice for a cycle."""
    from .graph.builder import DependencyGraphBuilder
    from .graph.analyzer import CycleAnalyzer
    from .parser.chunker import StructureAwareChunker
    from .knowledge.loader import PatternLoader
    from .rag.dual_kb import DualKnowledgeRAG
    from .llm.factory import get_llm
    from .explainer.generator import CycleExplainer
    
    # Build graph and find cycles
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Analyzing project...", total=None)
        builder = DependencyGraphBuilder(project_path)
        graph = builder.build()
        
        analyzer = CycleAnalyzer(graph)
        cycles = analyzer.find_all_cycles()
        progress.update(task, completed=True)
    
    if not cycles:
        console.print("[green]No cycles to explain![/green]")
        return
    
    cycle = analyzer.get_cycle_by_id(cycle_id)
    if not cycle:
        console.print(f"[red]Cycle {cycle_id} not found. Available: {[c.cycle_id for c in cycles]}[/red]")
        raise typer.Exit(1)
    
    console.print(f"\n[cyan]Analyzing Cycle {cycle_id}: {' → '.join(cycle.chain)}[/cyan]\n")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Chunk code
        task = progress.add_task("Chunking code...", total=None)
        chunker = StructureAwareChunker()
        all_chunks = []
        for file in cycle.files:
            file_path = project_path / file
            if file_path.exists():
                all_chunks.extend(chunker.chunk_file(file_path))
        progress.update(task, completed=True)
        
        # Load patterns
        task = progress.add_task("Loading patterns...", total=None)
        if patterns_dir is None:
            patterns_dir = Path(__file__).parent.parent / "knowledge_base" / "patterns"
        loader = PatternLoader(patterns_dir)
        patterns = loader.load_all()
        progress.update(task, completed=True)
        
        # Initialize RAG
        task = progress.add_task("Indexing knowledge base...", total=None)
        rag = DualKnowledgeRAG(use_chroma=False)  # In-memory for simplicity
        rag.index_code_chunks(all_chunks)
        rag.index_patterns(patterns)
        progress.update(task, completed=True)
        
        # Generate explanation
        task = progress.add_task("Generating explanation (this may take a while)...", total=None)
        llm = get_llm()
        explainer = CycleExplainer(rag, llm)
        
        try:
            explanation = explainer.explain_cycle_sync(cycle)
            progress.update(task, completed=True)
            
            console.print("\n[bold]Explanation:[/bold]\n")
            rprint(explanation)
        except Exception as e:
            progress.update(task, completed=True)
            console.print(f"[yellow]Warning: Could not generate LLM explanation: {e}[/yellow]")
            console.print("[yellow]Make sure Ollama is running with: ollama serve[/yellow]")


@app.command()
def init_patterns(
    output_dir: Path = typer.Option(
        Path("knowledge_base/patterns"),
        "-o", "--output",
        help="Output directory for pattern files"
    ),
):
    """Initialize default refactoring pattern files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create sample patterns
    patterns = _get_default_patterns()
    
    for name, content in patterns.items():
        file_path = output_dir / f"{name}.yaml"
        file_path.write_text(content)
        console.print(f"[green]✓[/green] Created {file_path}")
    
    console.print(f"\n[green]Initialized {len(patterns)} pattern files in {output_dir}[/green]")


def _get_default_patterns() -> dict[str, str]:
    """Get default pattern YAML content."""
    return {
        "extract_interface": """pattern_id: extract_interface
title: Extract Interface to Break Bidirectional Dependency
anti_pattern: bidirectional_association
refactoring_strategy: extract_interface
complexity: medium
framework: generic

problem_description: |
  Two modules directly import each other because they need to reference
  each other's types or call each other's methods.

symptoms:
  - ImportError depending on import order
  - Cannot import one module without the other
  - Circular import detected by static analysis

solution_description: |
  Extract the shared contract into a third module that both can import.

before_code: |
  # user_service.py
  from order_service import OrderService
  class UserService:
      def __init__(self):
          self.orders = OrderService()

  # order_service.py
  from user_service import UserService
  class OrderService:
      def __init__(self):
          self.users = UserService()

after_code: |
  # interfaces.py
  from typing import Protocol
  class UserServiceProtocol(Protocol):
      def get_user(self, id: int): ...

  # user_service.py
  from interfaces import OrderServiceProtocol
  class UserService:
      def __init__(self, orders: OrderServiceProtocol):
          self.orders = orders

step_by_step:
  - Identify shared types/interfaces
  - Create interfaces.py with Protocol classes
  - Update imports to use interfaces
  - Use dependency injection

keywords:
  - circular import
  - bidirectional
  - interface
  - protocol
  - dependency injection
""",
        "lazy_import": """pattern_id: lazy_import
title: Use Lazy Import to Break Cycle
anti_pattern: circular_dependency
refactoring_strategy: lazy_import
complexity: low
framework: generic

problem_description: |
  A module needs another module only inside specific functions,
  not at module load time.

symptoms:
  - Import only used in one function
  - Import could be deferred

solution_description: |
  Move the import inside the function that needs it.

before_code: |
  # a.py
  from b import helper  # Circular!
  def main():
      return helper()

after_code: |
  # a.py
  def main():
      from b import helper  # Local import
      return helper()

step_by_step:
  - Identify which functions use the import
  - Move import inside those functions
  - Test that behavior is unchanged

keywords:
  - lazy import
  - local import
  - deferred import
  - function-level import
""",
        "type_checking_guard": """pattern_id: type_checking_guard
title: Use TYPE_CHECKING for Type-Only Imports
anti_pattern: circular_dependency
refactoring_strategy: type_checking_guard
complexity: low
framework: generic

problem_description: |
  Import is only needed for type hints, not runtime behavior.

symptoms:
  - Import used only in type annotations
  - No runtime dependency on the module

solution_description: |
  Use typing.TYPE_CHECKING to guard the import.

before_code: |
  # a.py
  from b import SomeClass  # Circular!
  def process(obj: SomeClass) -> None:
      pass

after_code: |
  # a.py
  from typing import TYPE_CHECKING
  if TYPE_CHECKING:
      from b import SomeClass
  def process(obj: "SomeClass") -> None:
      pass

step_by_step:
  - Add TYPE_CHECKING import
  - Wrap type-only imports in if TYPE_CHECKING block
  - Use string annotations for forward references

keywords:
  - TYPE_CHECKING
  - type hints
  - forward reference
  - annotations
""",
    }

@app.command()
def chat(
    project_path: Path = typer.Argument(..., help="Path to Python project"),
):
    """Interactive chat to ask questions about your codebase."""
    from .chat import CodebaseChat
    
    if not project_path.exists():
        console.print(f"[red]Error: Path does not exist: {project_path}[/red]")
        raise typer.Exit(1)
    
    CodebaseChat(project_path).start_interactive()


if __name__ == "__main__":
    app()
