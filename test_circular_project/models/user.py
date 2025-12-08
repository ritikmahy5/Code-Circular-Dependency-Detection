"""User model with circular dependency on Order."""
from typing import List, Optional
from ..services.user_service import UserService  # Circular: models -> services -> models

class User:
    def __init__(self, user_id: int, name: str):
        self.user_id = user_id
        self.name = name
        self.orders: List['Order'] = []
    
    def get_order_history(self):
        from .order import Order  # Circular: user -> order -> user
        return Order.get_by_user(self.user_id)
    
    def validate(self):
        service = UserService()
        return service.validate_user(self)