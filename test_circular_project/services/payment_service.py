"""Payment service with circular dependency."""
from typing import TYPE_CHECKING
from .order_service import OrderService  # Circular: payment_service -> order_service -> payment_service

if TYPE_CHECKING:
    from ..models.order import Order

class PaymentService:
    def process_payment(self, order: 'Order') -> bool:
        # Payment processing logic
        return True
    
    def refund_order(self, order_id: int):
        order_service = OrderService()
        # Refund logic
        return True