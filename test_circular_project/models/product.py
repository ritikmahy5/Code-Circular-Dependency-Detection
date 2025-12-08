"""Product model with circular dependency on Order."""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .order import Order  # Type-checking only circular (less severe)

class Product:
    def __init__(self, product_id: int, name: str, price: float):
        self.product_id = product_id
        self.name = name
        self.price = price
    
    def get_recent_orders(self):
        from .order import Order  # Circular: product -> order -> product
        return Order.get_by_product(self.product_id)
    
    def validate_price(self):
        from ..utils.validator import Validator  # Circular: models -> utils -> models
        return Validator.validate_product(self)