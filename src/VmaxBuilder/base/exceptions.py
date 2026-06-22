class ModelStageContractError(Exception):
    pass


class ImplementationConfigConflictError(Exception):
    def __init__(
        self,
        *,
        key: str,
        config_a: type,
        config_b: type,
        file_a: str,
        file_b: str,
    ):
        super().__init__(
            f"Configuration key '{key}' is defined in both "
            f"{config_a.__name__} ({file_a}) and "
            f"{config_b.__name__} ({file_b})."
        )


class ConfigurationError(ValueError):
    """Generated: validation needed.

    Description:
        Base configuration validation error.

    Args:
        message (str): Human-readable error message.
    """


class UnknownOptionError(ConfigurationError):
    """Generated: validation needed.

    Description:
        Error raised when config contains unsupported option keys in strict mode.

    Args:
        message (str): Human-readable error message.
    """


class InvalidOptionValueError(ConfigurationError):
    """Generated: validation needed.

    Description:
        Error raised when config option value is outside allowed values.

    Args:
        message (str): Human-readable error message.
    """
