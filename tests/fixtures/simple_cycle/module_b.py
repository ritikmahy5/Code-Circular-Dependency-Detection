"""Module B - imports from Module A (creates cycle)."""
from module_a import process_a

def process_b(data):
    """Process data."""
    return f"processed_{data}"

def get_combined():
    """Get combined result (causes the cycle)."""
    return process_a("test")
