"""Models module with TYPE_CHECKING cycle."""
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from services import UserService

class User:
    """User model."""
    
    def __init__(self, name: str):
        self.name = name
    
    def get_service(self) -> "UserService":
        """Get associated service."""
        from services import UserService
        return UserService(self)
