# CS 6120 Requirements Fixes

## CRITICAL ISSUES TO ADDRESS

### 1. Database Size: Need 10k+ Persistent Entries ❌

**Current:** 4 YAML patterns + dynamic chunks (not persistent)
**Required:** 10k+ entries in a persistent database

**Solution Options:**

#### Option A: Pre-index Large Codebase (FASTEST)
```bash
# 1. Analyze Django and save to persistent DB
cd /Users/ritik/Desktop/NLP_Project
source venv/bin/activate

# 2. Create persistent storage script
# Create: src/database/persistent_store.py
# - Clone Django repo
# - Chunk all 5000+ files → 20k+ chunks
# - Store in ChromaDB/FAISS permanently
# - Load at startup instead of re-creating
```

**Implementation:**
```python
# src/database/persistent_store.py
from pathlib import Path
import chromadb
from src.parser.chunker import StructureAwareChunker
from src.rag.dual_kb import DualKnowledgeRAG

def build_persistent_database():
    """Build 10k+ entry database from Django codebase."""
    # Clone Django
    subprocess.run(["git", "clone", "https://github.com/django/django"])
    
    # Chunk all files
    chunker = StructureAwareChunker()
    all_chunks = []
    for py_file in Path("django").rglob("*.py"):
        chunks = chunker.chunk_file(py_file)
        all_chunks.extend(chunks)
    
    print(f"Created {len(all_chunks)} chunks")  # Should be 20k+
    
    # Store permanently
    client = chromadb.PersistentClient(path="./persistent_db")
    collection = client.create_collection("code_chunks")
    # ... add chunks
```

#### Option B: Expand Pattern Database (SLOWER)
```bash
# Scrape refactoring patterns from:
# - refactoring.guru (100+ patterns)
# - sourcemaking.com (50+ patterns)
# - Martin Fowler's catalog (100+ patterns)
# - Python-specific patterns (200+)

# Goal: 1000+ YAML patterns in knowledge_base/patterns/
```

#### Option C: Use Pre-built Code Database
```bash
# Download CodeSearchNet dataset
# 2M+ code functions across 6 languages
# Filter for Python → 400k+ functions
# Store as embeddings
```

**RECOMMENDATION: Choose Option A** (can be done in 1 hour)

---

### 2. Clickable Citations ❌

**Current:** Shows file paths as text
**Required:** Hyperlinks to source code

**Fix in src/web/streamlit_app.py:**

```python
# Around line 930 - Replace:
st.markdown(f"**File: `{module_path}`**")

# With:
if github_url:
    file_link = f"{github_url}/blob/main/{module_path}#L{start_line}"
    st.markdown(f"**File: [{module_path}]({file_link})** 📎")
else:
    st.markdown(f"**File: `{module_path}`** (local)")

# For patterns - Add around line 850:
pattern_source = cycle.get('pattern_used')
if pattern_source:
    pattern_file = f"knowledge_base/patterns/{pattern_source}.yaml"
    st.markdown(f"📚 [Refactoring Pattern: {pattern_source}]({github_url}/blob/main/{pattern_file})")
```

**Also add:**
```python
# Line number citations in code blocks
with open(file_path, 'r') as f:
    lines = f.readlines()
    for i, line in enumerate(lines[:30], start=1):
        if 'import' in line:
            st.markdown(f"[Line {i}]({github_url}/blob/main/{file_path}#L{i}): `{line.strip()}`")
```

---

### 3. Systems Diagram ⚠️

**Current:** Text description in report.tex
**Required:** Visual architecture diagram

**Create: docs/architecture.png**

```
┌─────────────┐
│   User      │
│  (Browser)  │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────┐
│   Streamlit Frontend        │
│  (src/web/streamlit_app.py) │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│   AST Parser                │
│  (src/parser/ast_parser.py) │ → Extract imports, handle TYPE_CHECKING
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│   Structure-Aware Chunker   │
│  (src/parser/chunker.py)    │ → Create semantic chunks
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│   Dependency Graph Builder  │
│  (src/graph/builder.py)     │ → NetworkX graph
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│   Cycle Analyzer            │
│  (Tarjan's SCC Algorithm)   │ → Find all cycles
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│   Dual Knowledge RAG        │
│  (src/rag/dual_kb.py)       │
│                             │
│  ┌───────────────────────┐  │
│  │ Code Chunks DB        │  │ ← FAISS Vector Store
│  │ (20k+ entries)        │  │
│  └───────────────────────┘  │
│                             │
│  ┌───────────────────────┐  │
│  │ Refactoring Patterns  │  │ ← YAML Knowledge Base
│  │ (1000+ patterns)      │  │
│  └───────────────────────┘  │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│   Ollama LLM                │
│  (CodeLlama 13B - Local)    │ → Generate explanations
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│   Response with Citations   │
│  - Severity scores          │
│  - Clickable file links     │
│  - Pattern references       │
└─────────────────────────────┘
```

**Tool to create diagram:**
```bash
# Option 1: Use draw.io (diagrams.net)
open https://app.diagrams.net/

# Option 2: Use Python
pip install diagrams
python create_architecture_diagram.py
```

---

## IMPLEMENTATION TIMELINE

### Day 1 (2 hours): Fix Database Size
1. Create `src/database/persistent_store.py`
2. Clone Django repo
3. Generate 20k+ chunks
4. Store in persistent ChromaDB/FAISS
5. Update app to load from persistent storage

### Day 2 (1 hour): Add Clickable Citations
1. Update `src/web/streamlit_app.py` lines 880-960
2. Add GitHub URL input field
3. Convert all file paths to hyperlinks
4. Add line number citations
5. Link pattern sources

### Day 3 (1 hour): Create Systems Diagram
1. Use draw.io or Python diagrams library
2. Create visual architecture diagram
3. Save as `docs/architecture.png`
4. Embed in report.tex and README.md

---

## VERIFICATION CHECKLIST

Before submission:
- [ ] Database has 10k+ entries (check with: `len(collection.get()['ids'])`)
- [ ] Frontend shows clickable links to files
- [ ] Frontend shows clickable links to patterns
- [ ] Systems diagram exists as image file
- [ ] Systems diagram embedded in report
- [ ] LLM confirmed running locally (no API keys needed)
- [ ] Team contributions section updated
- [ ] All code runs without errors

---

## QUICK TEST

```bash
cd /Users/ritik/Desktop/NLP_Project
source venv/bin/activate

# Test 1: Database size
python -c "
from src.database.persistent_store import get_database_size
size = get_database_size()
print(f'Database entries: {size}')
assert size >= 10000, f'Need 10k+ entries, only have {size}'
"

# Test 2: Citations
streamlit run src/web/streamlit_app.py
# Navigate to Analysis tab
# Verify file paths are clickable links

# Test 3: Ollama local
curl http://localhost:11434/api/generate -d '{"model":"codellama:13b","prompt":"test"}'
# Should return response without API key
```

---

## CONTACT FOR HELP

If stuck on any of these:
- Database: Use FAISS instead of ChromaDB (already in requirements.txt)
- Citations: Use st.markdown() with HTML <a> tags
- Diagram: Use Google Slides if coding is too complex
