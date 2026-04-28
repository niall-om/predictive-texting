from .base import AppError


class RepositoryError(AppError):
    """Base exception for repository/persistence failures."""


class BootstrapError(AppError):
    """Errors during application bootstrap/startup."""
