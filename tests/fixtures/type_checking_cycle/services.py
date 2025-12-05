"""Services module."""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models import User

class UserService:
    """Service for user operations."""
    
    def __init__(self, user: "User"):
        self.user = user
    
    def process(self) -> str:
        return f"Processing {self.user.name}"
