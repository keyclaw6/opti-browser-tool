class OptiEvalError(Exception):
    """Base error for expected runner failures."""


class ConfigurationError(OptiEvalError):
    """Raised when runner configuration is missing or malformed."""


class ValidationError(OptiEvalError):
    """Raised when suite or catalog validation fails."""
