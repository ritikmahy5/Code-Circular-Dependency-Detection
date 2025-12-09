"""Schemas for refactoring patterns knowledge base."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from pathlib import Path


class AntiPatternType(Enum):
    """Types of anti-patterns that cause circular dependencies."""
    CIRCULAR_DEPENDENCY = "circular_dependency"
    GOD_OBJECT = "god_object"
    TIGHT_COUPLING = "tight_coupling"
    BIDIRECTIONAL_ASSOCIATION = "bidirectional_association"
    LAYER_VIOLATION = "layer_violation"
    SHARED_MUTABLE_STATE = "shared_mutable_state"


class RefactoringStrategy(Enum):
    """Strategies for refactoring circular dependencies."""
    EXTRACT_INTERFACE = "extract_interface"
    DEPENDENCY_INJECTION = "dependency_injection"
    MEDIATOR_PATTERN = "mediator_pattern"
    EXTRACT_SHARED_MODULE = "extract_shared_module"
    LAZY_IMPORT = "lazy_import"
    TYPE_CHECKING_GUARD = "type_checking_guard"
    EVENT_DRIVEN = "event_driven"
    MERGE_MODULES = "merge_modules"


class Complexity(Enum):
    """Complexity levels for refactoring."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Framework(Enum):
    """Framework-specific patterns."""
    GENERIC = "generic"
    DJANGO = "django"
    FASTAPI = "fastapi"
    FLASK = "flask"
    PYTORCH = "pytorch"


@dataclass
class RefactoringPattern:
    """A refactoring pattern entry for the knowledge base."""
    
    # All fields with defaults to avoid ordering issues
    pattern_id: str = ""
    title: str = ""
    anti_pattern: AntiPatternType = AntiPatternType.CIRCULAR_DEPENDENCY
    refactoring_strategy: RefactoringStrategy = RefactoringStrategy.EXTRACT_INTERFACE
    complexity: Complexity = Complexity.MEDIUM
    problem_description: str = ""
    framework: Framework = Framework.GENERIC
    symptoms: list[str] = field(default_factory=list)
    solution_description: str = ""
    before_code: str = ""
    after_code: str = ""
    step_by_step: list[str] = field(default_factory=list)
    related_patterns: list[str] = field(default_factory=list)
    common_causes: list[str] = field(default_factory=list)
    pitfalls: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    
    # Source file for citations (added for proper RAG attribution)
    source_file: Optional[str] = None
    
    def to_embedding_text(self) -> str:
        """Generate text for embedding."""
        return f"""
Anti-pattern: {self.anti_pattern.value}
Strategy: {self.refactoring_strategy.value}
Framework: {self.framework.value}

Problem: {self.problem_description}

Symptoms: {', '.join(self.symptoms)}

Solution: {self.solution_description}

Keywords: {', '.join(self.keywords)}
"""
    
    def to_prompt_context(self) -> str:
        """Generate detailed context for LLM prompt."""
        steps = '\n'.join(f"  {i+1}. {step}" for i, step in enumerate(self.step_by_step))
        symptoms = '\n'.join(f"  - {s}" for s in self.symptoms)
        pitfalls = '\n'.join(f"  - {p}" for p in self.pitfalls)
        
        return f"""
## {self.title}

**Anti-pattern:** {self.anti_pattern.value}
**Strategy:** {self.refactoring_strategy.value}
**Complexity:** {self.complexity.value}

### Problem
{self.problem_description}

### Symptoms
{symptoms}

### Solution
{self.solution_description}

### Before (Anti-pattern)
```python
{self.before_code}
```

### After (Refactored)
```python
{self.after_code}
```

### Step-by-Step
{steps}

### Pitfalls to Avoid
{pitfalls}
"""
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "pattern_id": self.pattern_id,
            "title": self.title,
            "anti_pattern": self.anti_pattern.value,
            "refactoring_strategy": self.refactoring_strategy.value,
            "complexity": self.complexity.value,
            "framework": self.framework.value,
            "problem_description": self.problem_description,
            "symptoms": self.symptoms,
            "solution_description": self.solution_description,
            "before_code": self.before_code,
            "after_code": self.after_code,
            "step_by_step": self.step_by_step,
            "related_patterns": self.related_patterns,
            "common_causes": self.common_causes,
            "pitfalls": self.pitfalls,
            "keywords": self.keywords,
            "source_file": self.source_file,  # Include for citation tracking
        }


@dataclass
class CodeChunk:
    file_path: Path
    start_line: int
    end_line: int
    content: str
    chunk_type: str  # 'import', 'class', 'function', 'standalone'
    source: str = "user"  # 'user' or 'persistent_db'

    def __repr__(self):
        return f"CodeChunk({self.file_path}, {self.start_line}-{self.end_line}, type={self.chunk_type}, source={self.source})"
