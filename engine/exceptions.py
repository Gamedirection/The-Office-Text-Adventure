"""Custom exceptions used by the game engine."""


class EngineError(Exception):
    """Base error type for engine operations."""


class ValidationError(EngineError):
    """Raised when content validation fails."""
