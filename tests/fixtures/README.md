# Test Fixtures

This directory contains synthetic test projects for validating the circular dependency detector.

## Fixtures

- `simple_cycle/` - 2-file circular dependency
- `complex_cycle/` - 3+ file circular dependency
- `type_checking_cycle/` - Cycle using TYPE_CHECKING
- `local_import_cycle/` - Cycle with function-local imports
- `no_cycle/` - Clean project with no cycles

## Usage

```python
from pathlib import Path
from src.graph.builder import DependencyGraphBuilder

project = Path("tests/fixtures/simple_cycle")
builder = DependencyGraphBuilder(project)
graph = builder.build()
```
