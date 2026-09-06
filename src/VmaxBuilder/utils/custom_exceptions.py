"""
This module contains custom exceptions for the MetabolismModeler package.
"""

from collections.abc import Sequence
from typing import Any, Hashable
from warnings import warn

# todo add ability to check for options which are not compatible with each other

#  todo: add global exception hook
# # import logging
# # import sys
# # def handle_global_exception(exc_type, exc_value, exc_traceback):
# #     """Global hook to catch uncaught errors and write them to a file on crash."""
# #     # Ignore KeyboardInterrupt (Ctrl+C) so it doesn't pollute logs
# #     if issubclass(exc_type, KeyboardInterrupt):
# #         sys.__excepthook__(exc_type, exc_value, exc_traceback)
# #         return
# todo:
# #     # Set delay=True so the file is omitted until this exact block runs
# #     handler = logging.FileHandler("crash_report.log", delay=True)
# #     handler.setFormatter(
# #         logging.Formatter("%(asctime)s - GLOBAL_CRASH - %(message)s")
# #     )
# #
# todo:
# #     logger = logging.getLogger("global_error")
# #     logger.addHandler(handler)
# #
# todo:
# #     # Log the full unhandled exception stack
# #     logger.error(
# #         "An unhandled exception occurred",
# #         exc_info=(exc_type, exc_value, exc_traceback),
# #     )
# #
# #
# todo:
# # # Register the function as the system exception handler
# # sys.excepthook = handle_global_exception
# end todo:


def _check_and_return_value(  # noqa: C901
    dict_: dict[Hashable, Any],
    key_name: Hashable,
    options: Sequence[Any],
    ignore_missing_options: bool = False,
) -> Any:
    """Generated: validation needed.

    Description:
        Validate dictionary value against accepted options and special sentinels.

    Args:
        dict_ (dict[Hashable, Any]): Dictionary containing key-value pairs to check.
        key_name (Hashable): Key to look for in the dictionary.
        options (Sequence[Any]): Accepted options for the value.
        ignore_missing_options (bool): When True, warn instead of raising for missing keys.

    Returns:
        Any: Validated dictionary value.

    Raises:
        ExceptionIncorrectKwargs: When value is missing or invalid.
    """
    get_value = dict_.get(key_name, None)
    is_ANY = True if "ANY" in options else False
    is_OPTIONAL = True if "OPTIONAL" in options else False
    if get_value is None and ignore_missing_options:
        warn(
            f"The keyword argument '{key_name}' was not provided. The options are: "
            f"{options} Ignoring missing options: {ignore_missing_options}",
            stacklevel=2,
        )
        return None
    if get_value is None and not is_OPTIONAL:
        raise ExceptionIncorrectKwargs(
            key_name=key_name,
            get_value=get_value,
            options=options,
            special_case=None,
            ignore_missing_options=ignore_missing_options,
        )
    if is_ANY:
        return get_value
    if is_OPTIONAL and get_value is None:
        return get_value
    if isinstance(get_value, list):
        if any(item not in options for item in get_value):
            raise ExceptionIncorrectKwargs(
                key_name=key_name,
                get_value=get_value,
                options=options,
                special_case="list",
                ignore_missing_options=ignore_missing_options,
            )
        return get_value
    if any(
        [
            isinstance(option, tuple)
            and all(
                [
                    isinstance(opt, (int, float)) or opt == "inf" or opt == "-inf"
                    for opt in option
                ]
            )
            for option in options
        ]
    ):
        numeric_ranges = [
            tuple(float(opt) for opt in option)
            for option in options
            if isinstance(option, tuple)
            and all(isinstance(opt, (int, float)) or opt in {"inf", "-inf"} for opt in option)
        ]
        if numeric_ranges:
            for min_value, max_value in numeric_ranges:
                if isinstance(get_value, tuple) and len(get_value) == 2:
                    min_get_value, max_get_value = get_value
                    if (
                        min_value <= min_get_value <= max_value
                        and min_value <= max_get_value <= max_value
                    ):
                        return get_value
                elif isinstance(get_value, (int, float)):
                    if min_value <= get_value <= max_value:
                        return get_value
            raise ExceptionIncorrectKwargs(
                key_name=key_name,
                get_value=get_value,
                options=options,
                special_case="numeric",
                ignore_missing_options=ignore_missing_options,
            )
    if get_value not in options:
        raise ExceptionIncorrectKwargs(
            key_name=key_name,
            get_value=get_value,
            options=options,
            special_case=None,
            ignore_missing_options=ignore_missing_options,
        )
    return get_value


class ExceptionIncorrectKwargs(Exception):
    """
    Custom exception for missing keyword arguments during initialization of class
    instance. Used in check_and_return_value(dict_, key_name, options). Should
    provide a message indicating the possible options for the user to choose from
    and what they entered.
    """

    def __init__(
        self,
        key_name: Hashable,
        get_value: Any,
        options: Sequence[Any],
        special_case: str | None = None,
        ignore_missing_options: bool = False,
    ) -> None:
        """Generated: validation needed.

        Description:
            Build exception message for invalid keyword argument value.

        Args:
            key_name (Hashable): Name of keyword argument that is missing or incorrect.
            get_value (Any): Provided value for the keyword argument.
            options (Sequence[Any]): Valid options for the keyword argument.
            special_case (str | None): Special handling mode for list or numeric validation.
            ignore_missing_options (bool): When True, emit warning instead of raising.

        Returns:
            None: Initializes exception message and optional warning.
        """
        self.key_name = key_name
        self.get_value = get_value
        self.options = options
        if get_value is None:
            message = (
                f"The keyword argument '{key_name}' was not provided. "
                f"The options are: {options}"
            )
        elif special_case == "numeric":
            message = (
                f"The keyword argument '{key_name}' was provided with the value "
                f"'{get_value}' but it must be between the min and max of: {options}"
            )
        elif special_case == "list":
            get_values_not_in_options = set(item for item in get_value if item not in options)
            indices_in_get_value = [get_value.index(g) for g in get_values_not_in_options]
            message = (
                f"The keyword argument '{key_name}' was provided with the values in a "
                f"list: '{get_values_not_in_options}' at positions {indices_in_get_value}"
                f" but they are not valid options. The options for the elements are: "
                f"{options}"
            )
        else:
            message = (
                f"The keyword argument '{key_name}' was provided with the value "
                f"'{get_value}', but it is not a valid option. The options are: {options}"
            )
        if ignore_missing_options:
            message += f" Ignoring missing options: {ignore_missing_options}"
            warn(message, stacklevel=2)
            return

        super().__init__(message)


class SpecialTypeError(TypeError):
    """
    Custom TypeError which is raised when a function does not receive the expected
    arguments. This is used specifically when :func:`requires_loaded_files`
    decorator is used to load necessary files and insert them into the function
    arguments. These arguments are default None, yet are necesssary for the
    function to run.

    Thus this exception is raised when the function is called without the
    necessary arguments, but only occurs in the body of the function.
    """

    def __init__(self, message: str, missing_arguments: list[str]) -> None:
        self.missing_arguments = missing_arguments
        full_message = (
            f"{message}. Missing required arguments: {', '.join(self.missing_arguments)}"
        )
        super().__init__(full_message)
