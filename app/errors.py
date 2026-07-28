"""Stable application exceptions used across infrastructure boundaries."""


class AgentError(Exception):
    """Base class for expected Agent Runtime failures."""


class ConfigurationError(AgentError):
    """Runtime configuration is missing or invalid."""


class SessionNotFoundError(AgentError):
    """The requested session does not exist."""


class RepositoryError(AgentError):
    """Persistent state could not be read or written."""


class LLMError(AgentError):
    """Base class for external model failures."""


class LLMTimeoutError(LLMError):
    """The model endpoint did not respond before the configured timeout."""


class LLMHTTPError(LLMError):
    """The model endpoint returned a non-success status."""

    def __init__(self, status_code: int, message: str = "LLM request failed") -> None:
        super().__init__(message)
        self.status_code = status_code


class LLMProtocolError(LLMError):
    """The model response did not follow the expected protocol."""


class ToolError(AgentError):
    """Base class for tool failures."""


class ToolNotFoundError(ToolError):
    """A model requested an unregistered tool."""


class ToolValidationError(ToolError):
    """Tool arguments failed JSON or schema validation."""


class ToolExecutionError(ToolError):
    """A validated tool handler failed during execution."""


class MaxRoundsReached(AgentError):
    """The Agent Loop stopped at its configured round limit."""

