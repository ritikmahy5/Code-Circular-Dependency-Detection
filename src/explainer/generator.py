"""Generate explanations for detected cycles."""
from dataclasses import dataclass
from typing import Optional

from ..graph.analyzer import CycleInfo
from ..rag.dual_kb import DualKnowledgeRAG, RAGContext
from ..llm.base import BaseLLM


SYSTEM_PROMPT = """You are an expert software architect specializing in Python dependency management and refactoring. Your task is to analyze circular dependencies and provide actionable refactoring recommendations.

Be specific to the actual code provided. Reference specific class names, method names, and line numbers. Prioritize the simplest fix that breaks the cycle while maintaining clean architecture.

**IMPORTANT - Citation Requirements:**
- When recommending a refactoring approach, CITE the specific pattern from the Knowledge Base Sources that supports your recommendation
- Format citations as: "Based on the **[Pattern Title]** pattern..."
- If no patterns match, state: "Based on general software engineering best practices..."
- Do NOT cite the problematic code as a source - that is what we're analyzing, not a reference

Always structure your response with clear sections:
1. Root Cause Analysis
2. Impact Assessment  
3. Recommended Fix (with citations to patterns)
4. Step-by-Step Plan
5. Verification Steps"""


EXPLANATION_TEMPLATE = """Analyze this circular dependency and provide a refactoring plan.

## Detected Cycle

**Files involved:** {files}
**Import chain:** {chain}
**Severity:** {severity}
**Cycle length:** {length} files
**Coupling density:** {coupling:.2f}

## Edge Details
{edge_details}

## Retrieved Context
{rag_context}

## Your Task

Provide a detailed analysis and refactoring plan. Be specific about:
- Which exact imports need to change
- What new modules/interfaces to create (if any)
- The order of refactoring steps
- How to verify the fix works

Focus on the simplest solution that breaks the cycle while maintaining good architecture."""


class CycleExplainer:
    """Generate natural language explanations for cycles."""
    
    def __init__(self, rag: DualKnowledgeRAG, llm: BaseLLM):
        self.rag = rag
        self.llm = llm
    
    async def explain_cycle(self, cycle: CycleInfo) -> str:
        """Generate explanation for a single cycle."""
        
        # Build query for RAG retrieval
        query = self._build_query(cycle)
        
        # Retrieve context
        context = self.rag.retrieve(
            query=query,
            file_filter=cycle.files,
            n_code=min(10, len(cycle.files) * 2),
            n_patterns=3,
        )
        
        # Format edge details
        edge_details = self._format_edge_details(cycle)
        
        # Build prompt
        prompt = EXPLANATION_TEMPLATE.format(
            files=", ".join(cycle.files),
            chain=" → ".join(cycle.chain),
            severity=cycle.severity.value,
            length=cycle.length,
            coupling=cycle.coupling_density,
            edge_details=edge_details,
            rag_context=context.to_prompt(),
        )
        
        # Generate explanation
        response = await self.llm.generate(prompt, system=SYSTEM_PROMPT)
        
        return response.content
    
    def explain_cycle_sync(self, cycle: CycleInfo) -> str:
        """Synchronous version of explain_cycle."""
        import asyncio
        return asyncio.run(self.explain_cycle(cycle))
    
    def _build_query(self, cycle: CycleInfo) -> str:
        """Build semantic query from cycle info."""
        return f"""
Circular dependency involving {cycle.length} files.
Import chain: {' -> '.join(cycle.chain)}
Severity: {cycle.severity.value}
Files: {', '.join(cycle.files)}

Looking for refactoring patterns to break this circular import cycle.
"""
    
    def _format_edge_details(self, cycle: CycleInfo) -> str:
        """Format edge details for the prompt."""
        lines = []
        for edge in cycle.edge_details:
            flags = []
            if edge.get('type_checking'):
                flags.append("TYPE_CHECKING")
            if edge.get('local'):
                flags.append("local import")
            
            flag_str = f" ({', '.join(flags)})" if flags else ""
            lines.append(
                f"- `{edge['from']}` imports `{edge['to']}` "
                f"at line {edge.get('line', '?')}{flag_str}"
            )
        
        return "\n".join(lines) if lines else "No edge details available"
    
    async def generate_report(self, cycles: list[CycleInfo]) -> str:
        """Generate a full report for all cycles."""
        sections = ["# Circular Dependency Analysis Report\n"]
        
        sections.append(f"**Total cycles detected:** {len(cycles)}\n")
        
        # Summary by severity
        from collections import Counter
        severity_counts = Counter(c.severity.value for c in cycles)
        sections.append("## Summary by Severity\n")
        for severity, count in sorted(severity_counts.items()):
            sections.append(f"- **{severity}:** {count} cycles")
        sections.append("")
        
        # Detailed analysis for each cycle
        sections.append("## Detailed Analysis\n")
        
        for cycle in cycles:
            sections.append(f"### Cycle {cycle.cycle_id}: {' → '.join(cycle.chain[:3])}...\n")
            explanation = await self.explain_cycle(cycle)
            sections.append(explanation)
            sections.append("\n---\n")
        
        return "\n".join(sections)
