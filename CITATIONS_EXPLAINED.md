# What Is Being Cited? - Citation System Explanation

## Overview

Your project has **3 types of citations** that provide transparency and traceability:

---

## 1. 📍 **WHERE Citations** (Location/Source)
**What:** Links to the actual code files and line numbers  
**Purpose:** Show users exactly where to find the implementation

### Examples:

#### File-Level Citations
```
File: [models/user.py](https://github.com/ritikmahy5/.../blob/main/models/user.py) 📎
```
- **What it cites:** The actual Python source file in your repository
- **Where it links:** GitHub file viewer
- **Why it matters:** Users can click to see the full file context

#### Line-Level Citations
```python
from django.db import models  # [L3](https://github.com/.../models/user.py#L3)
from .base import BaseModel   # [L4](https://github.com/.../models/user.py#L4)
```
- **What it cites:** Specific line numbers in the file
- **Where it links:** GitHub file viewer, scrolled to exact line
- **Why it matters:** Pinpoint the exact import causing the circular dependency

---

## 2. 🧠 **WHAT Citations** (Methodology/Algorithm)
**What:** Links to the algorithms and methods used to detect problems  
**Purpose:** Explain how the tool works and provide educational value

### Examples:

#### Detection Algorithm Citation
```
📚 Detected using Tarjan's SCC Algorithm
   Link: src/graph/analyzer.py
```
- **What it cites:** The implementation of Tarjan's Strongly Connected Components algorithm
- **Where it links:** `src/graph/analyzer.py` (your implementation)
- **Why it matters:** 
  - Proves you're using a correct, well-known algorithm
  - Shows it's not just "magic" - it's computer science
  - CS 6120 requirement: cite your methodology

#### Severity Scoring Citation
```
📚 Scored by Severity Calculator
   Link: src/scoring/severity.py
```
- **What it cites:** The multi-factor scoring algorithm
- **Where it links:** `src/scoring/severity.py` (your implementation)
- **Why it matters:**
  - Explains how severity scores are calculated
  - Shows the 4 factors: length, coupling, centrality, import type
  - Transparency in how problems are prioritized

#### Pattern Matching Citation
```
📚 Refactoring Patterns
   Link: knowledge_base/patterns/
```
- **What it cites:** Your 4 refactoring pattern YAML files
- **Where it links:** `knowledge_base/patterns/` directory
- **What's there:**
  - `lazy_import.yaml` - How to defer imports
  - `type_checking_guard.yaml` - TYPE_CHECKING pattern
  - `extract_interface.yaml` - Interface extraction
  - `dependency_injection.yaml` - Dependency injection
- **Why it matters:** Shows your solutions are based on documented patterns

---

## 3. 💡 **WHY Citations** (Problem Classification)
**What:** Explains what type of problem it is  
**Purpose:** Educational - helps users understand the nature of the issue

### Examples:

#### Problem Type Classification
```
🔍 Problem Type: Direct Circular Dependency (A → B → A)
📚 Detected using Tarjan's SCC Algorithm | Scored by Severity Calculator
```

- **What it cites:** 
  - Classification: Self-Cycle vs Direct vs Indirect
  - Algorithm used: Tarjan's SCC
  - Scoring method: Multi-factor calculator
- **Why it matters:**
  - Users learn what type of circular dependency they have
  - Different types need different fixes
  - Links back to the methodology (WHAT citations)

---

## Complete Citation Flow (Example)

Let's trace a full example:

### User sees a circular dependency:

```
🔴 Cycle 1 | Severity: 8/10 | Size: 3 modules

🔍 Problem Type: Indirect Circular Dependency (Chain of 3 modules)
📚 Detected using [Tarjan's SCC Algorithm](github.com/.../src/graph/analyzer.py)
   | Scored by [Severity Calculator](github.com/.../src/scoring/severity.py)

📦 Module Path:
models/user.py → models/team.py → models/organization.py → models/user.py

📄 Affected Files:
File: [models/user.py](github.com/.../models/user.py) 📎
  from .team import Team  # [L5](github.com/.../models/user.py#L5)

File: [models/team.py](github.com/.../models/team.py) 📎
  from .organization import Organization  # [L3](github.com/.../models/team.py#L3)

File: [models/organization.py](github.com/.../models/organization.py) 📎
  from .user import User  # [L8](github.com/.../models/organization.py#L8)

💡 Refactoring Suggestions:
1. Use lazy imports (defer until needed)
   📚 Pattern: [lazy_import.yaml](github.com/.../knowledge_base/patterns/lazy_import.yaml)
```

### What Gets Cited:

| Citation Type | What It Links To | Purpose |
|--------------|------------------|---------|
| **WHERE** | `models/user.py` line 5 | Show exact import location |
| **WHERE** | `models/team.py` line 3 | Show exact import location |
| **WHERE** | `models/organization.py` line 8 | Show exact import location |
| **WHAT** | `src/graph/analyzer.py` | Explain detection algorithm |
| **WHAT** | `src/scoring/severity.py` | Explain severity calculation |
| **WHAT** | `knowledge_base/patterns/lazy_import.yaml` | Provide solution pattern |
| **WHY** | "Indirect Circular Dependency" | Classify the problem type |

---

## CS 6120 Requirements ✅

### Requirement: "Clickable citations"
**You provide:**
1. ✅ Clickable file citations → GitHub file viewer
2. ✅ Clickable line citations → GitHub line anchors
3. ✅ Clickable algorithm citations → Source code
4. ✅ Clickable pattern citations → YAML documentation

### Requirement: "Show sources of information"
**You provide:**
1. ✅ WHERE: File paths and line numbers
2. ✅ WHAT: Algorithm implementations
3. ✅ WHY: Problem classifications
4. ✅ HOW: Refactoring patterns

---

## Technical Implementation

### How GitHub URLs are Generated:

```python
# Example from streamlit_app.py
github_url = st.session_state.github_url  # e.g., "https://github.com/ritikmahy5/repo"
rel_path = file_path.relative_to(project_path)  # e.g., "models/user.py"

# File citation
file_url = f"{github_url}/blob/main/{rel_path}"
# Result: https://github.com/ritikmahy5/repo/blob/main/models/user.py

# Line citation  
line_url = f"{github_url}/blob/main/{rel_path}#L{line_num}"
# Result: https://github.com/ritikmahy5/repo/blob/main/models/user.py#L5

# Algorithm citation
algo_url = f"{github_url}/blob/main/src/graph/analyzer.py"
# Result: https://github.com/ritikmahy5/repo/blob/main/src/graph/analyzer.py
```

---

## Summary: What's Being Cited?

| What | Example | Purpose |
|------|---------|---------|
| **Source files** | `models/user.py` | Show where problem exists |
| **Specific lines** | Line 5 in user.py | Pinpoint exact import |
| **Detection algorithm** | `src/graph/analyzer.py` | Explain how it was found |
| **Scoring logic** | `src/scoring/severity.py` | Explain severity calculation |
| **Solution patterns** | `lazy_import.yaml` | Provide fix guidance |
| **Problem types** | "Direct Circular Dependency" | Classify the issue |

---

## Why This Matters for CS 6120

1. **Transparency:** Users can verify your methodology
2. **Education:** Users learn about algorithms and patterns
3. **Trust:** Everything is traceable to source code
4. **Reproducibility:** Anyone can see exactly how it works
5. **Academic Integrity:** You cite your sources and methods

Your citation system is comprehensive and goes beyond typical tools! 🎯
