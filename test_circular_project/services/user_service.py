"""User service with circular dependency on models."""
from ..models.user import User  # Circular: services -> models -> services
from .order_service import OrderService  # Circular: user_service -> order_service -> user_service

class UserService:
    def validate_user(self, user: User) -> bool:
        # Validation logic
        return len(user.name) > 0
    
    def get_user_orders(self, user_id: int):
        order_service = OrderService()
        return order_service.get_user_orders(user_id)