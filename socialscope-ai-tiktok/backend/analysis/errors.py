class AnalysisError(Exception):
    """A user-facing problem with the input. Carries an HTTP status and machine-readable code."""

    def __init__(self, message, code="invalid_input", status=422, details=None):
        super().__init__(message)
        self.message, self.code, self.status, self.details = message, code, status, details
