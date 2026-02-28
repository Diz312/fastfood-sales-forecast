class ForecastError(Exception):
    """Base exception for forecasting errors."""


class DataNotFoundError(ForecastError):
    """Raised when expected data is missing."""


class ModelTrainingError(ForecastError):
    """Raised when model training fails."""


class ReconciliationError(ForecastError):
    """Raised when hierarchical reconciliation fails."""


class AgentError(ForecastError):
    """Raised when an agent tool call fails."""
