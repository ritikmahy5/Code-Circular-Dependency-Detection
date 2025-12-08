"""Validator with circular dependency on models."""
from ..models.product import Product  # Circular: utils -> models -> utils
from .formatter import Formatter  # Circular: validator -> formatter -> validator

class Validator:
    @staticmethod
    def validate_product(product: Product) -> bool:
        return product.price > 0
    
    @staticmethod
    def validate_string(value: str) -> bool:
        formatter = Formatter()
        formatted = formatter.format_string(value)
        return len(formatted) > 0