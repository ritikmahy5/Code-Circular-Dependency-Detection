"""Order model with circular dependency on User and Product."""
from typing import Optional
from .user import User  # Circular: order -> user -> order
from .product import Product  # Circular: order -> product -> order

class Order:
    def __init__(self, order_id: int, user: User, product: Product):
        self.order_id = order_id
        self.user = user
        self.product = product
    
    @classmethod
    def get_by_user(cls, user_id: int):
        # This would typically query a database
        return []
    
    @classmethod
    def get_by_product(cls, product_id: int):
        # This would typically query a database
        return []
    
    def process(self):
        from ..services.order_service import OrderService  # Circular: models -> services -> models
        service = OrderService()
        return service.process_order(self)