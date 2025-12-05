"""Module A - imports from Module B."""
from module_b import process_b

def process_a(data):
    """Process data using module B."""
    return process_b(data) + "_from_a"
