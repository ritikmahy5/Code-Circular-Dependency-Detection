"""Natural Language Query Interface for Codebase Analysis."""
import asyncio
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Prompt

from .graph.builder import DependencyGraphBuilder
from .graph.analyzer import CycleAnalyzer
from .parser.chunker import StructureAwareChunker
from .rag.dual_kb import DualKnowledgeRAG
from .llm.factory import get_llm
from .knowledge.loader import PatternLoader

class CodebaseChat:
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.console = Console()
        self.console.print("[dim]Loading...[/dim]")
        self.builder = DependencyGraphBuilder(project_path)
        self.graph = self.builder.build()
        self.analyzer = CycleAnalyzer(self.graph)
        self.cycles = self.analyzer.find_all_cycles()
        self.chunker = StructureAwareChunker()
        self.chunks = []
        failed_files = []
        for fp in project_path.rglob("*.py"):
            try:
                self.chunks.extend(self.chunker.chunk_file(fp))
            except (SyntaxError, UnicodeDecodeError):
                # Expected errors for malformed files - track but continue
                failed_files.append(str(fp.name))
            except Exception as e:
                # Unexpected errors - log with warning
                self.console.print(f"[yellow]Warning: Could not chunk {fp.name}: {e}[/yellow]")
        
        if failed_files:
            self.console.print(f"[dim]Skipped {len(failed_files)} files with parsing errors[/dim]")
        
        self.rag = DualKnowledgeRAG(use_chroma=False)
        self.rag.index_code_chunks(self.chunks)
        patterns_dir = Path(__file__).parent.parent / "knowledge_base" / "patterns"
        if patterns_dir.exists():
            loader = PatternLoader(patterns_dir)
            self.rag.index_patterns(loader.load_all())
        self.llm = get_llm()
        self.console.print(f"[green]Loaded {self.graph.number_of_nodes()} files, {len(self.cycles)} cycles[/green]\n")

    def _get_summary(self):
        return f"Files: {self.graph.number_of_nodes()}, Cycles: {len(self.cycles)}"

    async def ask(self, question: str) -> str:
        ctx = self.rag.retrieve(query=question, n_code=5, n_patterns=2)
        prompt = f"""Codebase: {self.project_path}
{self._get_summary()}

{ctx.to_prompt()}

Question: {question}"""
        resp = await self.llm.generate(prompt, system="You are a code analyst expert.")
        return resp.content

    def ask_sync(self, question: str) -> str:
        return asyncio.run(self.ask(question))

    def start_interactive(self):
        self.console.print("[bold cyan]Codebase Chat[/bold cyan] (type 'quit' to exit)\n")
        while True:
            try:
                q = Prompt.ask("[green]You[/green]")
                if q.lower() in ['quit', 'exit', 'q']:
                    break
                if not q.strip():
                    continue
                with self.console.status("[dim]Thinking...[/dim]"):
                    resp = self.ask_sync(q)
                self.console.print(f"\n[blue]Assistant[/blue]")
                self.console.print(Markdown(resp))
                self.console.print()
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")
