"""Exception raised when a specific version of a resource is not found."""


class VersionNotFoundError(Exception):
    """Raised when a specific version of a resource (prompt, contract, etc.) is not found."""
    
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)