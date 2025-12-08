"""Order service with circular dependencies."""
from ..models.order import Order  # Circular: services -> models -> services
from .user_service import UserService  # Circular: order_service -> user_service -> order_service
from .payment_service import PaymentService  # Circular: order_service -> payment_service -> order_service

class OrderService:
    def process_order(self, order: Order) -> bool:
        user_service = UserService()
        if not user_service.validate_user(order.user):
            return False
        
        payment_service = PaymentService()
        return payment_service.process_payment(order)
    
    def get_user_orders(self, user_id: int):
        return Order.get_by_user(user_id)