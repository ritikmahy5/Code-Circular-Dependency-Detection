"""Load refactoring patterns from YAML files."""
import yaml
from pathlib import Path
from typing import Iterator

from .schemas import (
    RefactoringPattern,
    AntiPatternType,
    RefactoringStrategy,
    Complexity,
    Framework,
)


class PatternLoader:
    """Loads refactoring patterns from YAML files."""
    
    def __init__(self, patterns_dir: Path):
        self.patterns_dir = patterns_dir
        self._patterns: dict[str, RefactoringPattern] = {}
    
    def load_all(self) -> list[RefactoringPattern]:
        """Load all patterns from the directory."""
        self._patterns = {}
        
        if not self.patterns_dir.exists():
            print(f"Warning: Patterns directory not found: {self.patterns_dir}")
            return []
        
        for yaml_file in self.patterns_dir.glob("*.yaml"):
            try:
                pattern = self._load_file(yaml_file)
                self._patterns[pattern.pattern_id] = pattern
            except Exception as e:
                print(f"Warning: Could not load {yaml_file}: {e}")
        
        return list(self._patterns.values())
    
    def _load_file(self, file_path: Path) -> RefactoringPattern:
        """Load a single pattern from a YAML file."""
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
        
        return RefactoringPattern(
            pattern_id=data.get('pattern_id', file_path.stem),
            title=data['title'],
            anti_pattern=AntiPatternType(data['anti_pattern']),
            refactoring_strategy=RefactoringStrategy(data['refactoring_strategy']),
            complexity=Complexity(data.get('complexity', 'medium')),
            framework=Framework(data.get('framework', 'generic')),
            problem_description=data.get('problem_description', ''),
            symptoms=data.get('symptoms', []),
            solution_description=data.get('solution_description', ''),
            before_code=data.get('before_code', ''),
            after_code=data.get('after_code', ''),
            step_by_step=data.get('step_by_step', []),
            related_patterns=data.get('related_patterns', []),
            common_causes=data.get('common_causes', []),
            pitfalls=data.get('pitfalls', []),
            keywords=data.get('keywords', []),
        )
    
    def get_pattern(self, pattern_id: str) -> RefactoringPattern | None:
        """Get a pattern by ID."""
        return self._patterns.get(pattern_id)
    
    def get_patterns_by_strategy(
        self, 
        strategy: RefactoringStrategy
    ) -> list[RefactoringPattern]:
        """Get all patterns for a given strategy."""
        return [
            p for p in self._patterns.values()
            if p.refactoring_strategy == strategy
        ]
    
    def get_patterns_by_complexity(
        self, 
        complexity: Complexity
    ) -> list[RefactoringPattern]:
        """Get all patterns for a given complexity level."""
        return [
            p for p in self._patterns.values()
            if p.complexity == complexity
        ]
