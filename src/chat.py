"""Natural Language Query Interface for Codebase Analysis."""
import asyncio
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Prompt

from .graph.builder import DependencyGraphBuilder
from .graph.analyzer import CycleAnalyzer, CycleInfo
from .parser.chunker import StructureAwareChunker
from .rag.dual_kb import DualKnowledgeRAG, RAGContext, create_rag_with_persistent_db
from .llm.factory import get_llm
from .knowledge.loader import PatternLoader

import networkx as nx


class CodebaseChat:
    """Interactive chat interface with RAG-powered responses.
    
    Optimized for fast initialization by:
    1. Reusing existing graph/cycles if provided
    2. Only chunking files involved in cycles (not entire project)
    3. Lazy loading of embeddings
    """
    
    def __init__(
        self, 
        project_path: Path, 
        use_persistent_db: bool = False,
        # Optional: reuse existing analysis results
        existing_graph: Optional[nx.DiGraph] = None,
        existing_cycles: Optional[list] = None,
        max_files_to_chunk: int = 50,  # Limit for speed
    ):
        """
        Initialize CodebaseChat.
        
        Args:
            project_path: Path to the project to analyze
            use_persistent_db: Whether to load the 42k Django knowledge base
            existing_graph: Reuse graph from previous analysis (saves ~10s)
            existing_cycles: Reuse cycles from previous analysis
            max_files_to_chunk: Max files to chunk (0 = all, default 50 for speed)
        """
        self.project_path = Path(project_path)
        self.console = Console()
        self.max_files_to_chunk = max_files_to_chunk
        
        # Reuse existing analysis or build new
        if existing_graph is not None:
            self.graph = existing_graph
            self.cycles = existing_cycles or []
            self.console.print("[dim]Using existing analysis results...[/dim]")
        else:
            self.console.print("[dim]Building dependency graph...[/dim]")
            self.builder = DependencyGraphBuilder(self.project_path)
            self.graph = self.builder.build()
            self.analyzer = CycleAnalyzer(self.graph)
            self.cycles = self.analyzer.find_all_cycles()
        
        # Initialize RAG (fast - no embeddings yet)
        self.console.print("[dim]Initializing RAG system...[/dim]")
        
        if use_persistent_db:
            try:
                self.console.print("[yellow]⚠️ Loading 42k knowledge base - this may take 2-5 minutes on GCP...[/yellow]")
                self.rag = create_rag_with_persistent_db(
                    use_chroma=False,
                    load_patterns=True,
                    max_chunks=1000,  # Further reduced for GCP speed (was 5000, then 2000)
                )
            except Exception as e:
                self.console.print(f"[yellow]Warning: Could not load persistent DB: {e}[/yellow]")
                self.rag = DualKnowledgeRAG(use_chroma=False, load_persistent_db=False)
                self._load_patterns_only()
        else:
            # Lightweight mode - just patterns, no persistent DB
            self.rag = DualKnowledgeRAG(use_chroma=False, load_persistent_db=False)
            self._load_patterns_only()
        
        # Chunk ONLY cycle-related files (much faster than entire project)
        self._chunk_cycle_files()
        
        # Get LLM (lazy - just stores config)
        self.console.print("[dim]Connecting to LLM...[/dim]")
        self.llm = get_llm()
        
        # Show summary
        stats = self.rag.get_stats()
        self.console.print(f"\n[green]✅ Chat Ready![/green]")
        self.console.print(f"   • Project chunks: {stats['user_chunks']:,}")
        self.console.print(f"   • Knowledge base: {stats['persistent_chunks_loaded']:,} chunks")
        self.console.print(f"   • Patterns: {stats['patterns']}")
        self.console.print(f"   • Cycles found: {len(self.cycles)}\n")
    
    def _chunk_cycle_files(self):
        """Chunk only files involved in cycles (fast) instead of entire project."""
        self.chunks = []
        
        # Get files involved in cycles
        cycle_files = set()
        for cycle in self.cycles:
            if hasattr(cycle, 'files'):
                cycle_files.update(cycle.files)
            elif isinstance(cycle, dict) and 'modules' in cycle:
                cycle_files.update(cycle['modules'])
        
        # Find actual file paths
        files_to_chunk = []
        for rel_path in cycle_files:
            full_path = self.project_path / rel_path
            if full_path.exists():
                files_to_chunk.append(full_path)
        
        # If no cycle files found, sample some Python files
        if not files_to_chunk:
            all_py = list(self.project_path.rglob("*.py"))
            files_to_chunk = all_py[:self.max_files_to_chunk] if self.max_files_to_chunk > 0 else all_py[:20]
        
        # Limit total files for speed
        if self.max_files_to_chunk > 0 and len(files_to_chunk) > self.max_files_to_chunk:
            files_to_chunk = files_to_chunk[:self.max_files_to_chunk]
        
        self.console.print(f"[dim]Chunking {len(files_to_chunk)} files (cycle-related)...[/dim]")
        
        chunker = StructureAwareChunker()
        for fp in files_to_chunk:
            try:
                self.chunks.extend(chunker.chunk_file(fp))
            except Exception:
                pass  # Skip problematic files
        
        # Index chunks
        if self.chunks:
            self.rag.index_code_chunks(self.chunks, replace=True)
    
    def _load_patterns_only(self):
        """Load just the refactoring patterns without persistent DB."""
        patterns_dir = Path(__file__).parent.parent / "knowledge_base" / "patterns"
        if patterns_dir.exists():
            try:
                loader = PatternLoader(patterns_dir)
                patterns = loader.load_all()
                self.rag.index_patterns(patterns)
                self.console.print(f"[dim]Loaded {len(patterns)} refactoring patterns[/dim]")
            except Exception as e:
                self.console.print(f"[yellow]Warning: Could not load patterns: {e}[/yellow]")

    def _get_summary(self):
        return f"Files: {self.graph.number_of_nodes()}, Cycles: {len(self.cycles)}"

    async def ask(self, question: str) -> tuple[str, RAGContext]:
        """Ask a question about the codebase."""
        # Retrieve context from RAG
        ctx = self.rag.retrieve(
            query=question, 
            n_code=5, 
            n_patterns=2,
        )
        
        # Build prompt with RAG context
        prompt = f"""Codebase: {self.project_path}
{self._get_summary()}

{ctx.to_prompt()}

Question: {question}"""
        
        resp = await self.llm.generate(prompt, system="You are a code analyst expert specializing in fixing circular dependencies.")
        return resp.content, ctx

    def ask_sync(self, question: str) -> tuple[str, RAGContext]:
        """Synchronous version of ask()."""
        return asyncio.run(self.ask(question))

    def start_interactive(self):
        """Start interactive chat session."""
        self.console.print("[bold cyan]Codebase Chat[/bold cyan] (type 'quit' to exit)")
        self.console.print("[dim]Ask questions about circular dependencies, refactoring, or your codebase.[/dim]")
        self.console.print("[dim]Type 'stats' to see RAG database statistics.[/dim]\n")
        
        while True:
            try:
                q = Prompt.ask("[green]You[/green]")
                if q.lower() in ['quit', 'exit', 'q']:
                    break
                if not q.strip():
                    continue
                    
                # Special commands
                if q.lower() == 'stats':
                    stats = self.rag.get_stats()
                    self.console.print("\n[bold]📊 RAG Database Statistics:[/bold]")
                    self.console.print(f"  Pre-built chunks: {stats['persistent_chunks_loaded']:,}")
                    self.console.print(f"  Project chunks: {stats['user_chunks']:,}")
                    self.console.print(f"  Patterns: {stats['patterns']}")
                    self.console.print(f"  Total searchable: {stats['total_entries']:,}\n")
                    continue
                
                with self.console.status("[dim]Thinking...[/dim]"):
                    resp, ctx = self.ask_sync(q)
                
                self.console.print(f"\n[blue]Assistant[/blue]")
                self.console.print(Markdown(resp))
                
                # Show sources used
                sources = []
                if ctx.from_persistent_db > 0:
                    sources.append(f"{ctx.from_persistent_db} from knowledge base")
                if ctx.from_user_project > 0:
                    sources.append(f"{ctx.from_user_project} from your project")
                if ctx.refactoring_patterns:
                    patterns_used = [p.title for p in ctx.refactoring_patterns]
                    sources.append(f"patterns: {', '.join(patterns_used)}")
                
                if sources:
                    self.console.print(f"[dim]📚 Sources: {'; '.join(sources)}[/dim]")
                
                self.console.print()
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")
