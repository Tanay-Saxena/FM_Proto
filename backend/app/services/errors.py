class DomainError(Exception):
    def __init__(self, code: str, message: str, status: int = 409, detail: dict | list | None = None):
        super().__init__(message)
        self.code, self.message, self.status, self.detail = code, message, status, detail
