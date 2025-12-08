"""Formatter with circular dependency on validator."""
from .validator import Validator  # Circular: formatter -> validator -> formatter

class Formatter:
    def format_string(self, value: str) -> str:
        # Don't validate in formatter to avoid infinite loop
        return value.strip().lower()
    
    def format_and_validate(self, value: str) -> tuple[str, bool]:
        formatted = self.format_string(value)
        # This would cause infinite recursion if actually called
        # is_valid = Validator.validate_string(formatted)
        is_valid = len(formatted) > 0  # Simplified to avoid runtime error
        return formatted, is_valid