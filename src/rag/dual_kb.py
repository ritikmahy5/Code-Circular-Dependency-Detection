"""Dual knowledge base RAG system."""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import json

from .embeddings import EmbeddingModel
from ..parser.chunker import CodeChunk
from ..knowledge.schemas import RefactoringPattern


@dataclass
class RAGContext:
    """Combined context from both knowledge bases."""
    code_chunks: list[CodeChunk]
    refactoring_patterns: list[RefactoringPattern]
    
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
        
        return f"""
## Relevant Code from the Codebase

{code_section}

## Relevant Refactoring Patterns

{pattern_section}
"""


class DualKnowledgeRAG:
    """RAG system with separate code and pattern collections."""
    
    def __init__(
        self, 
        persist_dir: Optional[Path] = None,
        use_chroma: bool = True
    ):
        self.encoder = EmbeddingModel()
        self.persist_dir = persist_dir
        self.use_chroma = use_chroma
        
        self._code_chunks: list[CodeChunk] = []
        self._code_embeddings: list[list[float]] = []
        
        self._patterns: list[RefactoringPattern] = []
        self._pattern_embeddings: list[list[float]] = []
        
        if use_chroma:
            self._init_chroma()
    
    def _init_chroma(self):
        """Initialize ChromaDB collections."""
        try:
            import chromadb
            
            if self.persist_dir:
                self.client = chromadb.PersistentClient(path=str(self.persist_dir))
            else:
                self.client = chromadb.Client()
            
            self.code_collection = self.client.get_or_create_collection(
                name="code_chunks",
                metadata={"hnsw:space": "cosine"}
            )
            self.pattern_collection = self.client.get_or_create_collection(
                name="refactoring_patterns",
                metadata={"hnsw:space": "cosine"}
            )
        except ImportError:
            print("ChromaDB not available, using in-memory storage")
            self.use_chroma = False
    
    def index_code_chunks(self, chunks: list[CodeChunk]) -> None:
        """Index code chunks for retrieval."""
        if not chunks:
            return
        
        self._code_chunks = chunks
        texts = [c.to_embedding_text() for c in chunks]
        embeddings = self.encoder.encode(texts)
        self._code_embeddings = embeddings.tolist()
        
        if self.use_chroma:
            # Clear existing and add new
            try:
                self.code_collection.delete(where={})
            except:
                pass
            
            self.code_collection.add(
                ids=[c.chunk_id for c in chunks],
                embeddings=self._code_embeddings,
                documents=texts,
                metadatas=[{
                    "file_path": c.file_path,
                    "chunk_type": c.chunk_type.value,
                    "name": c.name,
                } for c in chunks]
            )
    
    def index_patterns(self, patterns: list[RefactoringPattern]) -> None:
        """Index refactoring patterns for retrieval."""
        if not patterns:
            return
        
        self._patterns = patterns
        texts = [p.to_embedding_text() for p in patterns]
        embeddings = self.encoder.encode(texts)
        self._pattern_embeddings = embeddings.tolist()
        
        if self.use_chroma:
            try:
                self.pattern_collection.delete(where={})
            except:
                pass
            
            self.pattern_collection.add(
                ids=[p.pattern_id for p in patterns],
                embeddings=self._pattern_embeddings,
                documents=texts,
                metadatas=[{
                    "anti_pattern": p.anti_pattern.value,
                    "strategy": p.refactoring_strategy.value,
                    "complexity": p.complexity.value,
                } for p in patterns]
            )
    
    def retrieve(
        self, 
        query: str,
        file_filter: Optional[list[str]] = None,
        n_code: int = 5,
        n_patterns: int = 3
    ) -> RAGContext:
        """Retrieve relevant context for a query."""
        query_embedding = self.encoder.encode_single(query)
        
        # Retrieve code chunks
        code_chunks = self._retrieve_code(query_embedding, file_filter, n_code)
        
        # Retrieve patterns
        patterns = self._retrieve_patterns(query_embedding, n_patterns)
        
        return RAGContext(
            code_chunks=code_chunks,
            refactoring_patterns=patterns,
        )
    
    def _retrieve_code(
        self, 
        query_embedding, 
        file_filter: Optional[list[str]],
        n: int
    ) -> list[CodeChunk]:
        """Retrieve code chunks."""
        if self.use_chroma and self.code_collection.count() > 0:
            where = None
            if file_filter:
                where = {"file_path": {"$in": file_filter}}
            
            results = self.code_collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=n,
                where=where,
            )
            
            # Map back to CodeChunk objects
            chunks = []
            for chunk_id in results['ids'][0]:
                for chunk in self._code_chunks:
                    if chunk.chunk_id == chunk_id:
                        chunks.append(chunk)
                        break
            return chunks
        else:
            # In-memory similarity search
            return self._similarity_search(
                query_embedding,
                self._code_chunks,
                self._code_embeddings,
                n,
                file_filter,
            )
    
    def _retrieve_patterns(self, query_embedding, n: int) -> list[RefactoringPattern]:
        """Retrieve refactoring patterns."""
        if self.use_chroma and self.pattern_collection.count() > 0:
            results = self.pattern_collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=n,
            )
            
            patterns = []
            for pattern_id in results['ids'][0]:
                for pattern in self._patterns:
                    if pattern.pattern_id == pattern_id:
                        patterns.append(pattern)
                        break
            return patterns
        else:
            return self._similarity_search(
                query_embedding,
                self._patterns,
                self._pattern_embeddings,
                n,
            )
    
    def _similarity_search(
        self,
        query_embedding,
        items: list,
        embeddings: list,
        n: int,
        file_filter: Optional[list[str]] = None,
    ) -> list:
        """Simple cosine similarity search."""
        import numpy as np
        
        if not embeddings:
            return []
        
        query_np = np.array(query_embedding)
        embeddings_np = np.array(embeddings)
        
        # Cosine similarity
        similarities = np.dot(embeddings_np, query_np) / (
            np.linalg.norm(embeddings_np, axis=1) * np.linalg.norm(query_np)
        )
        
        # Filter and sort
        indexed = list(enumerate(similarities))
        
        if file_filter and hasattr(items[0], 'file_path'):
            indexed = [
                (i, s) for i, s in indexed 
                if items[i].file_path in file_filter
            ]
        
        indexed.sort(key=lambda x: -x[1])
        
        return [items[i] for i, _ in indexed[:n]]
