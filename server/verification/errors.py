class VerificationError(Exception):
    def __init__(self, code, message, status=400, **details):
        self.code, self.message, self.status, self.details = code, message, status, details
        super().__init__(message)


def require(condition, code, message, status=400):
    if not condition:
        raise VerificationError(code, message, status)
