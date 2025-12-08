"""Main entry point."""
from models.user import User
from models.product import Product
from models.order import Order
from services.order_service import OrderService

def main():
    # Create instances
    user = User(1, "John Doe")
    product = Product(1, "Laptop", 999.99)
    order = Order(1, user, product)
    
    # Process order
    service = OrderService()
    success = service.process_order(order)
    
    print(f"Order processed: {success}")

if __name__ == "__main__":
    main()