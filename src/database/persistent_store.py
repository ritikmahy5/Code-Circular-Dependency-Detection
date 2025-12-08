"""
Persistent database for code chunks and refactoring patterns.
Creates a 10k+ entry database by pre-analyzing large codebases.
"""
import json
import pickle
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

from src.parser.chunker import StructureAwareChunker, CodeChunk
from src.knowledge.loader import PatternLoader

logger = logging.getLogger(__name__)


class PersistentDatabase:
    """Manages persistent storage of code chunks and patterns."""
    
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        
        self.chunks_file = self.db_path / "code_chunks.pkl"
        self.patterns_file = self.db_path / "patterns.json"
        self.metadata_file = self.db_path / "metadata.json"
        
    def save_chunks(self, chunks: List[CodeChunk]):
        """Save code chunks to persistent storage."""
        logger.info(f"Saving {len(chunks)} chunks to {self.chunks_file}")
        with open(self.chunks_file, 'wb') as f:
            pickle.dump(chunks, f)
    
    def load_chunks(self) -> List[CodeChunk]:
        """Load code chunks from persistent storage."""
        if not self.chunks_file.exists():
            logger.warning(f"Chunks file not found: {self.chunks_file}")
            return []
        
        logger.info(f"Loading chunks from {self.chunks_file}")
        with open(self.chunks_file, 'rb') as f:
            chunks = pickle.load(f)
        logger.info(f"Loaded {len(chunks)} chunks")
        return chunks
    
    def save_patterns(self, patterns: List[Dict[str, Any]]):
        """Save refactoring patterns to persistent storage."""
        logger.info(f"Saving {len(patterns)} patterns to {self.patterns_file}")
        with open(self.patterns_file, 'w') as f:
            json.dump(patterns, f, indent=2)
    
    def load_patterns(self) -> List[Dict[str, Any]]:
        """Load refactoring patterns from persistent storage."""
        if not self.patterns_file.exists():
            logger.warning(f"Patterns file not found: {self.patterns_file}")
            return []
        
        logger.info(f"Loading patterns from {self.patterns_file}")
        with open(self.patterns_file, 'r') as f:
            patterns = json.load(f)
        logger.info(f"Loaded {len(patterns)} patterns")
        return patterns
    
    def save_metadata(self, metadata: Dict[str, Any]):
        """Save database metadata."""
        with open(self.metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def load_metadata(self) -> Dict[str, Any]:
        """Load database metadata."""
        if not self.metadata_file.exists():
            return {}
        
        with open(self.metadata_file, 'r') as f:
            return json.load(f)
    
    def get_size(self) -> int:
        """Get total number of entries in database."""
        chunks = self.load_chunks()
        patterns = self.load_patterns()
        return len(chunks) + len(patterns)
    
    def exists(self) -> bool:
        """Check if database exists."""
        return self.chunks_file.exists() and self.patterns_file.exists()


def clone_repository(repo_url: str, target_dir: Path) -> Path:
    """Clone a git repository to target directory."""
    logger.info(f"Cloning {repo_url} to {target_dir}")
    
    # Use subprocess to clone
    result = subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(target_dir)],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"Failed to clone repository: {result.stderr}")
    
    logger.info(f"Successfully cloned to {target_dir}")
    return target_dir


def chunk_codebase(codebase_path: Path, max_files: Optional[int] = None) -> List[CodeChunk]:
    """
    Chunk all Python files in a codebase.
    
    Args:
        codebase_path: Path to the codebase
        max_files: Maximum number of files to process (None = all)
    
    Returns:
        List of code chunks
    """
    logger.info(f"Chunking codebase at {codebase_path}")
    
    chunker = StructureAwareChunker()
    all_chunks = []
    
    # Find all Python files
    python_files = list(codebase_path.rglob("*.py"))
    logger.info(f"Found {len(python_files)} Python files")
    
    if max_files:
        python_files = python_files[:max_files]
        logger.info(f"Processing first {max_files} files")
    
    # Chunk each file
    for i, py_file in enumerate(python_files, 1):
        if i % 100 == 0:
            logger.info(f"Processed {i}/{len(python_files)} files, {len(all_chunks)} chunks so far")
        
        try:
            chunks = chunker.chunk_file(py_file)
            all_chunks.extend(chunks)
        except Exception as e:
            logger.warning(f"Failed to chunk {py_file}: {e}")
            continue
    
    logger.info(f"Created {len(all_chunks)} total chunks from {len(python_files)} files")
    logger.info(f"Average {len(all_chunks)/len(python_files):.1f} chunks per file")
    
    return all_chunks


def build_database(
    db_path: Path,
    repo_url: str = "https://github.com/django/django",
    max_files: Optional[int] = 5000,
    force_rebuild: bool = False
) -> PersistentDatabase:
    """
    Build a persistent database with 10k+ entries.
    
    Args:
        db_path: Path to store the database
        repo_url: GitHub repository to analyze (default: Django)
        max_files: Maximum number of files to process
        force_rebuild: Rebuild even if database exists
    
    Returns:
        PersistentDatabase instance
    """
    db = PersistentDatabase(db_path)
    
    # Check if database already exists
    if db.exists() and not force_rebuild:
        logger.info(f"Database already exists at {db_path}")
        logger.info(f"Total entries: {db.get_size()}")
        return db
    
    logger.info(f"Building database at {db_path}")
    
    # Create temp directory for cloning
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Clone repository
        logger.info(f"Step 1/3: Cloning repository {repo_url}")
        repo_path = clone_repository(repo_url, tmpdir_path / "repo")
        
        # Chunk all files
        logger.info(f"Step 2/3: Chunking codebase (max {max_files} files)")
        chunks = chunk_codebase(repo_path, max_files=max_files)
        
        # Save chunks
        logger.info(f"Step 3/3: Saving to database")
        db.save_chunks(chunks)
    
    # Load and save patterns
    logger.info("Loading refactoring patterns")
    patterns_dir = Path(__file__).parent.parent.parent / "knowledge_base" / "patterns"
    
    all_patterns = []
    if patterns_dir.exists():
        pattern_loader = PatternLoader(patterns_dir)
        patterns_list = pattern_loader.load_all()
        for pattern in patterns_list:
            all_patterns.append(pattern.to_dict())
        logger.info(f"Loaded {len(all_patterns)} refactoring patterns")
    
    db.save_patterns(all_patterns)
    
    # Save metadata
    metadata = {
        "repo_url": repo_url,
        "num_chunks": len(chunks),
        "num_patterns": len(all_patterns),
        "total_entries": len(chunks) + len(all_patterns),
        "max_files_processed": max_files,
    }
    db.save_metadata(metadata)
    
    logger.info("=" * 60)
    logger.info(f"✅ Database built successfully!")
    logger.info(f"  - Code chunks: {len(chunks):,}")
    logger.info(f"  - Patterns: {len(all_patterns)}")
    logger.info(f"  - Total entries: {len(chunks) + len(all_patterns):,}")
    logger.info(f"  - Location: {db_path}")
    logger.info("=" * 60)
    
    return db


def load_database(db_path: Path) -> Optional[PersistentDatabase]:
    """
    Load an existing persistent database.
    
    Args:
        db_path: Path to the database
    
    Returns:
        PersistentDatabase instance or None if not found
    """
    db = PersistentDatabase(db_path)
    
    if not db.exists():
        logger.warning(f"Database not found at {db_path}")
        return None
    
    metadata = db.load_metadata()
    logger.info(f"Loaded database from {db_path}")
    logger.info(f"  - Total entries: {metadata.get('total_entries', 0):,}")
    logger.info(f"  - Code chunks: {metadata.get('num_chunks', 0):,}")
    logger.info(f"  - Patterns: {metadata.get('num_patterns', 0)}")
    
    return db


if __name__ == "__main__":
    """Build database when run directly."""
    import sys
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Build database
    db_path = Path(__file__).parent.parent.parent / "persistent_db"
    
    print("\n" + "=" * 60)
    print("Building Persistent Database for CS 6120 Project")
    print("=" * 60)
    print(f"Target: 10,000+ entries")
    print(f"Source: Django codebase (~5000 files)")
    print(f"Location: {db_path}")
    print("=" * 60 + "\n")
    
    try:
        db = build_database(
            db_path=db_path,
            repo_url="https://github.com/django/django",
            max_files=5000,
            force_rebuild="--rebuild" in sys.argv
        )
        
        # Verify size
        total_size = db.get_size()
        print(f"\n✅ SUCCESS: Database has {total_size:,} entries")
        
        if total_size < 10000:
            print(f"⚠️  WARNING: Database has less than 10,000 entries")
            print(f"   Consider increasing max_files or adding more repositories")
        else:
            print(f"✅ VERIFIED: Database meets 10k+ requirement!")
        
    except Exception as e:
        print(f"\n❌ ERROR: Failed to build database: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
