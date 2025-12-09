"""Dual knowledge base RAG system with persistent database support."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List
import json
import pickle
import logging
import hashlib
import random
import numpy as np

from .embeddings import EmbeddingModel
from ..parser.chunker import CodeChunk
from ..knowledge.schemas import RefactoringPattern

logger = logging.getLogger(__name__)


@dataclass
class RAGContext:
    """Combined context from both knowledge bases."""
    code_chunks: list[CodeChunk] = field(default_factory=list)
    refactoring_patterns: list[RefactoringPattern] = field(default_factory=list)
    
    # Track sources for proper citation
    from_persistent_db: int = 0  # Count of chunks from pre-built DB
    from_user_project: int = 0   # Count of chunks from user's project
    
    def to_prompt(self) -> str:
        """Generate prompt context from retrieved items."""
        code_section = "\n\n".join(
            f"### {chunk.context_header}\n```python\n{chunk.source_code}\n```"
            for chunk in self.code_chunks
        )
        
        pattern_section = "\n\n".join(
            pattern.to_prompt_context()
            for pattern in self.refactoring_patterns
        )
        
        sections = []
        
        if self.code_chunks:
            sections.append(f"""## Code Being Analyzed (Problem Context)

The following code sections are relevant to your query:

{code_section}""")
        
        if self.refactoring_patterns:
            sections.append(f"""## Knowledge Base Sources (Cite These in Recommendations)

The following refactoring patterns from the knowledge base are relevant:

{pattern_section}""")
        else:
            sections.append("""## Knowledge Base Sources

No specific patterns matched. Use general software engineering best practices.""")
        
        return "\n\n".join(sections)

    def to_streamlit_display(
        self, 
        github_url: Optional[str] = None, 
        cdd_github_url: str = "https://github.com/ritikmahy5/Code-Circular-Dependency-Detection"
    ) -> str:
        """Generate display for Streamlit with proper citations."""
        output = []

        if self.code_chunks:
            output.append("<h4>🔍 Code Analyzed:</h4>")
            if self.from_persistent_db > 0 or self.from_user_project > 0:
                output.append(f"<p><em>Retrieved {len(self.code_chunks)} chunks "
                            f"({self.from_persistent_db} from knowledge base, "
                            f"{self.from_user_project} from current project)</em></p>")
            output.append("<ul>")
            for chunk in self.code_chunks:
                file_path_str = str(chunk.file_path)
                
                # Check if this is from persistent DB (Django KB)
                if chunk.source == 'persistent_db' or "django" in file_path_str.lower():
                    # Extract clean Django path from the file_path
                    # Handle paths like "/var/folders/.../T/tmpXXX/repo/tests/..." -> "tests/..."
                    if "/repo/" in file_path_str:
                        # Extract everything after "/repo/"
                        clean_path = file_path_str.split("/repo/")[-1]
                    elif "django" in file_path_str.lower():
                        # Find the 'django' part and everything after it
                        django_path_parts = file_path_str.split('django')
                        if len(django_path_parts) > 1:
                            clean_path = 'django' + django_path_parts[-1]
                            clean_path = clean_path.lstrip('/')
                        else:
                            clean_path = file_path_str
                    else:
                        clean_path = file_path_str
                    
                    django_url = f"https://github.com/django/django/blob/main/{clean_path}#L{chunk.start_line}-L{chunk.end_line}"
                    link_text = f"{Path(clean_path).name} (Lines {chunk.start_line}-{chunk.end_line})"
                    output.append(f'<li><a href="{django_url}" target="_blank">📄 {link_text}</a> <em>(Django KB)</em></li>')
                elif github_url:
                    # User project chunk - need to extract relative path
                    try:
                        # Extract relative path from repo root
                        # Handle paths like: /var/folders/.../repo_123/scipy/sparse/_dok.py -> scipy/sparse/_dok.py
                        relative_path = file_path_str
                        
                        # Common patterns to extract relative path
                        if "/repo_" in file_path_str:
                            # Pattern: .../repo_TIMESTAMP/actual/path
                            parts = file_path_str.split("/repo_")
                            if len(parts) > 1:
                                # Get everything after the repo directory
                                after_repo = parts[1].split("/", 1)
                                if len(after_repo) > 1:
                                    relative_path = after_repo[1]
                        elif "/extracted/" in file_path_str:
                            # Pattern: .../extracted/actual/path
                            relative_path = file_path_str.split("/extracted/", 1)[-1]
                        elif "/clone/" in file_path_str:
                            # Pattern: .../clone/actual/path
                            relative_path = file_path_str.split("/clone/", 1)[-1]
                        
                        # Build clean GitHub URL
                        line_link = f"{github_url}/blob/main/{relative_path}#L{chunk.start_line}-L{chunk.end_line}"
                        link_text = f"{Path(relative_path).name} (Lines {chunk.start_line}-{chunk.end_line})"
                        output.append(f'<li><a href="{line_link}" target="_blank">📄 {link_text}</a></li>')
                    except (ValueError, AttributeError) as e:
                        # Fallback to plain text if something goes wrong
                        output.append(f"<li>📄 {Path(file_path_str).name} (Lines {chunk.start_line}-{chunk.end_line})</li>")
                else:
                    # No GitHub URL available, show plain text
                    output.append(f"<li>📄 {Path(file_path_str).name} (Lines {chunk.start_line}-{chunk.end_line})</li>")
            output.append("</ul>")

        if self.refactoring_patterns:
            output.append("<h4>📚 Sources Cited for Recommendations:</h4>")
            output.append("<ul>")
            for pattern in self.refactoring_patterns:
                strategy = pattern.refactoring_strategy.value.replace("_", " ").title()
                complexity = pattern.complexity.value
                pattern_filename = f"{pattern.pattern_id}.yaml"
                pattern_url = f"{cdd_github_url}/blob/main/knowledge_base/patterns/{pattern_filename}"
                
                output.append(
                    f'<li>'
                    f'<a href="{pattern_url}" target="_blank"><strong>📖 {pattern.title}</strong></a><br/>'
                    f'<em>Source:</em> <a href="{pattern_url}" target="_blank"><code>knowledge_base/patterns/{pattern_filename}</code></a><br/>'
                    f'<em>Strategy:</em> {strategy} · '
                    f'<em>Complexity:</em> {complexity} · '
                    f'<em>Anti-pattern:</em> {pattern.anti_pattern.value}'
                    f'</li>'
                )
            output.append("</ul>")
        
        if not self.refactoring_patterns:
            output.append("<p><em>⚠️ No matching refactoring patterns found in knowledge base.</em></p>")

        return "\n".join(output)


class DualKnowledgeRAG:
    """RAG system with persistent database support (42k+ code chunks)."""
    
    DEFAULT_PERSISTENT_DB = Path(__file__).parent.parent.parent / "persistent_db"
    
    def __init__(
        self, 
        persist_dir: Optional[Path] = None,
        use_chroma: bool = False,
        load_persistent_db: bool = True,
        max_persistent_chunks: int = 0,  # 0 = load ALL chunks (42,660)
    ):
        # Use CPU for stability (MPS can have issues with meta tensors)
        self.encoder = EmbeddingModel(device="cpu")
        self.persist_dir = persist_dir
        self.use_chroma = use_chroma
        self.max_persistent_chunks = max_persistent_chunks
        
        # Separate storage for pre-built vs user chunks
        self._persistent_chunks: list[CodeChunk] = []
        self._persistent_embeddings: list[list[float]] = []
        self._persistent_loaded = False
        
        self._user_chunks: list[CodeChunk] = []
        self._user_embeddings: list[list[float]] = []
        
        self._patterns: list[RefactoringPattern] = []
        self._pattern_embeddings: list[list[float]] = []
        
        # Metadata
        self.metadata = {}
        
        # Stats
        self.stats = {
            "persistent_chunks_available": 0,
            "persistent_chunks_loaded": 0,
            "user_chunks": 0,
            "patterns": 0,
        }
        
        if use_chroma:
            self._init_chroma()
        
        if load_persistent_db:
            self._load_persistent_database()
    
    def _init_chroma(self):
        """Initialize ChromaDB collections."""
        try:
            import chromadb
            if self.persist_dir:
                self.client = chromadb.PersistentClient(path=str(self.persist_dir))
            else:
                self.client = chromadb.Client()
            
            self.code_collection = self.client.get_or_create_collection(
                name="code_chunks", metadata={"hnsw:space": "cosine"}
            )
            self.pattern_collection = self.client.get_or_create_collection(
                name="refactoring_patterns", metadata={"hnsw:space": "cosine"}
            )
        except ImportError:
            print("ChromaDB not available, using in-memory storage")
            self.use_chroma = False
    
    def _load_persistent_database(self) -> bool:
        """Load pre-built database with 42k+ code chunks."""
        db_path = self.DEFAULT_PERSISTENT_DB
        
        if not db_path.exists():
            logger.warning(f"Persistent database not found at {db_path}")
            return False
        
        chunks_file = db_path / "code_chunks.pkl"
        embeddings_file = db_path / "code_embeddings.pkl"
        metadata_file = db_path / "metadata.json"
        
        if not chunks_file.exists():
            logger.warning(f"Code chunks file not found: {chunks_file}")
            return False
        
        try:
            # Load metadata
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    self.metadata = json.load(f)
                self.stats["persistent_chunks_available"] = self.metadata.get('num_chunks', 0)
                print(f"📚 Found persistent database: {self.metadata.get('num_chunks', 0):,} chunks from {self.metadata.get('repo_url', 'unknown')}")
            
            # Load chunks
            print(f"Loading code chunks from persistent database...")
            with open(chunks_file, 'rb') as f:
                all_chunks = pickle.load(f)
            
            # Set the source for each chunk
            for chunk in all_chunks:
                chunk.source = "persistent_db"

            if self.max_persistent_chunks > 0 and len(all_chunks) > self.max_persistent_chunks:
                # Sample diverse chunks (every Nth chunk)
                step = len(all_chunks) // self.max_persistent_chunks
                self._persistent_chunks = all_chunks[::step][:self.max_persistent_chunks]
                print(f"  Sampled {len(self._persistent_chunks):,} chunks from {len(all_chunks):,} available")
            else:
                # Load ALL chunks
                self._persistent_chunks = all_chunks
                print(f"  Loading ALL {len(all_chunks):,} chunks")
            
            self.stats["persistent_chunks_loaded"] = len(self._persistent_chunks)
            
            # Try to load pre-computed embeddings
            if embeddings_file.exists():
                print(f"Loading pre-computed embeddings...")
                with open(embeddings_file, 'rb') as f:
                    saved_embeddings = pickle.load(f)
                
                # Match embeddings to loaded chunks
                if len(saved_embeddings) == len(self._persistent_chunks):
                    self._persistent_embeddings = saved_embeddings
                    print(f"  Loaded {len(self._persistent_embeddings):,} pre-computed embeddings")
                elif len(saved_embeddings) >= len(self._persistent_chunks):
                    # We sampled chunks, need to sample embeddings too
                    if self.max_persistent_chunks > 0:
                        step = len(all_chunks) // self.max_persistent_chunks
                        self._persistent_embeddings = saved_embeddings[::step][:len(self._persistent_chunks)]
                    else:
                        self._persistent_embeddings = saved_embeddings[:len(self._persistent_chunks)]
                    print(f"  Loaded {len(self._persistent_embeddings):,} pre-computed embeddings")
                else:
                    print(f"  Embedding count mismatch ({len(saved_embeddings)} vs {len(self._persistent_chunks)}), will compute on-demand")
                    self._persistent_embeddings = []
            else:
                print(f"  No pre-computed embeddings found, will compute on first query")
                self._persistent_embeddings = []
            
            self._persistent_loaded = True
            print(f"✅ Persistent database loaded: {len(self._persistent_chunks):,} chunks ready")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load persistent database: {e}")
            print(f"⚠️ Could not load persistent database: {e}")
            return False
    
    def _ensure_persistent_embeddings(self):
        """Compute embeddings for persistent chunks if not already loaded."""
        if self._persistent_chunks and not self._persistent_embeddings:
            print(f"Computing embeddings for {len(self._persistent_chunks):,} persistent chunks...")
            texts = [c.to_embedding_text() for c in self._persistent_chunks]
            embeddings = self.encoder.encode(texts)
            self._persistent_embeddings = embeddings.tolist()
            
            # Save for future use
            embeddings_file = self.DEFAULT_PERSISTENT_DB / "code_embeddings.pkl"
            try:
                with open(embeddings_file, 'wb') as f:
                    pickle.dump(self._persistent_embeddings, f)
                print(f"  Saved embeddings to {embeddings_file}")
            except Exception as e:
                print(f"  Could not save embeddings: {e}")
    
    def index_code_chunks(self, chunks: list[CodeChunk], replace: bool = True) -> None:
        """Index user's project code chunks."""
        if not chunks:
            return
        
        if replace:
            self._user_chunks = chunks
        else:
            self._user_chunks.extend(chunks)
        
        self.stats["user_chunks"] = len(self._user_chunks)
        
        # Generate embeddings for user chunks
        texts = [c.to_embedding_text() for c in self._user_chunks]
        embeddings = self.encoder.encode(texts)
        self._user_embeddings = embeddings.tolist()
        
        print(f"✅ Indexed {len(chunks)} user project chunks")
    
    def index_patterns(self, patterns: list[RefactoringPattern]) -> None:
        """Index refactoring patterns."""
        if not patterns:
            return
        
        self._patterns = patterns
        self.stats["patterns"] = len(patterns)
        
        texts = [p.to_embedding_text() for p in patterns]
        embeddings = self.encoder.encode(texts)
        self._pattern_embeddings = embeddings.tolist()
    
    def get_stats(self) -> dict:
        """Get database statistics."""
        return {
            "persistent_chunks_available": self.metadata.get('num_chunks', 0) if self.metadata else 0,
            "persistent_chunks_loaded": len(self._persistent_chunks),
            "user_chunks": len(self._user_chunks),
            "total_code_chunks": len(self._persistent_chunks) + len(self._user_chunks),
            "patterns": len(self._patterns),
            "total_entries": len(self._persistent_chunks) + len(self._user_chunks) + len(self._patterns)
        }

    def retrieve(
        self, 
        query: str,
        n_code: int = 5,
        n_patterns: int = 3,
        min_from_kb: int = 0,  # Ensure at least N results from knowledge base
    ) -> RAGContext:
        """Retrieve relevant context for a query.
        
        Searches BOTH user project chunks AND persistent knowledge base,
        ensuring diversity in sources for better citations.
        """
        query_embedding = self.encoder.encode_single(query)
        
        # Ensure persistent embeddings are computed
        self._ensure_persistent_embeddings()
        
        # Debug: print what we have
        print(f"[RAG] Searching: {len(self._user_chunks)} user chunks, {len(self._persistent_chunks)} persistent chunks")
        
        # Get top results from EACH source separately
        user_results = []
        persistent_results = []
        
        # Search user chunks
        if self._user_chunks and self._user_embeddings:
            user_scores = self._get_similarity_scores(query_embedding, self._user_embeddings)
            user_indexed = [(score, self._user_chunks[i]) for i, score in enumerate(user_scores)]
            user_indexed.sort(key=lambda x: -x[0])  # Sort by score descending
            user_results = user_indexed
        
        # Search persistent chunks
        if self._persistent_chunks and self._persistent_embeddings:
            persistent_scores = self._get_similarity_scores(query_embedding, self._persistent_embeddings)
            persistent_indexed = [(score, self._persistent_chunks[i]) for i, score in enumerate(persistent_scores)]
            persistent_indexed.sort(key=lambda x: -x[0])  # Sort by score descending
            persistent_results = persistent_indexed
        
        # Combine and select the best results with diversity
        final_code_chunks = []
        
        # Ensure minimum from knowledge base if requested
        if min_from_kb > 0 and persistent_results:
            num_to_add = min(min_from_kb, len(persistent_results))
            final_code_chunks.extend([chunk for score, chunk in persistent_results[:num_to_add]])
            # Remove these from persistent_results to avoid duplication
            persistent_results = persistent_results[num_to_add:]

        # Combine remaining results and sort globally by score
        combined_results = user_results + persistent_results
        combined_results.sort(key=lambda x: -x[0])  # Sort by score descending

        # Add remaining chunks until we reach n_code
        remaining_needed = n_code - len(final_code_chunks)
        for score, chunk in combined_results[:remaining_needed]:
            if chunk not in final_code_chunks:
                final_code_chunks.append(chunk)

        # Pattern retrieval
        pattern_results = []
        if self._patterns and self._pattern_embeddings:
            pattern_scores = self._get_similarity_scores(query_embedding, self._pattern_embeddings)
            pattern_results = sorted(zip(pattern_scores, self._patterns), key=lambda x: -x[0])
            final_patterns = [pattern for score, pattern in pattern_results[:n_patterns]]
        else:
            final_patterns = []

        # Count sources
        from_user = sum(1 for chunk in final_code_chunks if chunk.source == 'user')
        from_kb = sum(1 for chunk in final_code_chunks if chunk.source == 'persistent_db')

        print(f"[RAG] Retrieved: {from_user} from user, {from_kb} from knowledge base")

        return RAGContext(
            code_chunks=final_code_chunks,
            refactoring_patterns=final_patterns,
            from_user_project=from_user,
            from_persistent_db=from_kb
        )

    def _get_similarity_scores(self, query_embedding: list[float], chunk_embeddings: list[list[float]]) -> list[float]:
        """Calculates cosine similarity between a query and a list of chunk embeddings."""
        if not chunk_embeddings:
            return []
        
        # Convert to numpy for efficient computation
        query_np = np.array(query_embedding, dtype=np.float32)
        chunk_np = np.array(chunk_embeddings, dtype=np.float32)

        # Normalize vectors
        query_norm = query_np / np.linalg.norm(query_np)
        chunk_norms = np.linalg.norm(chunk_np, axis=1)
        
        # Avoid division by zero for zero-length vectors
        chunk_norms[chunk_norms == 0] = 1e-9
        
        normalized_chunks = chunk_np / chunk_norms[:, np.newaxis]
        
        # Compute cosine similarity (dot product of normalized vectors)
        similarities = np.dot(normalized_chunks, query_norm)
        
        return similarities.tolist()
    
    def _similarity_search(
        self,
        query_embedding,
        items: list,
        embeddings: list,
        n: int,
        file_filter: Optional[list[str]] = None,
    ) -> list:
        """Cosine similarity search."""
        import numpy as np
        
        if not embeddings or not items:
            return []
        
        query_np = np.array(query_embedding)
        embeddings_np = np.array(embeddings)
        
        # Cosine similarity
        norms = np.linalg.norm(embeddings_np, axis=1) * np.linalg.norm(query_np)
        norms = np.where(norms == 0, 1e-10, norms)  # Avoid division by zero
        similarities = np.dot(embeddings_np, query_np) / norms
        
        # Get top indices
        indexed = list(enumerate(similarities))
        
        if file_filter and items and hasattr(items[0], 'file_path'):
            indexed = [(i, s) for i, s in indexed if items[i].file_path in file_filter]
        
        indexed.sort(key=lambda x: -x[1])
        
        return [items[i] for i, _ in indexed[:n]]


def create_rag_with_persistent_db(
    use_chroma: bool = False,
    load_patterns: bool = True,
    max_chunks: int = 0,  # 0 = load ALL 42,660 chunks
) -> DualKnowledgeRAG:
    """Factory function to create RAG with persistent database."""
    rag = DualKnowledgeRAG(
        use_chroma=use_chroma,
        load_persistent_db=True,
        max_persistent_chunks=max_chunks,
    )
    
    if load_patterns:
        patterns_dir = Path(__file__).parent.parent.parent / "knowledge_base" / "patterns"
        if patterns_dir.exists():
            from ..knowledge.loader import PatternLoader
            loader = PatternLoader(patterns_dir)
            patterns = loader.load_all()
            rag.index_patterns(patterns)
            print(f"✅ Loaded {len(patterns)} refactoring patterns")
    
    stats = rag.get_stats()
    print(f"\n📊 RAG Database Summary:")
    print(f"   • Knowledge base: {stats['persistent_chunks_loaded']:,} / {stats['persistent_chunks_available']:,} chunks loaded")
    print(f"   • Patterns: {stats['patterns']}")
    print(f"   • Total searchable entries: {stats['total_entries']:,}\n")
    
    return rag
