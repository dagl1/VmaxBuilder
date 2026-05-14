"""
This module contains custom exceptions for the MetabolismModeler package.
"""

from typing import Any, Hashable, List, Optional
from warnings import warn

# todo add ability to check for options which are not compatible with eachother


def _check_and_return_value(
    dict_: dict,
    key_name: Hashable,
    options: List[Any],
    ignore_missing_options: Optional[bool] = False,
) -> Any:
    """
    Checks if the value for the given key_name in the dictionary is valid according to the provided options.
    If the value is not found or is not valid, it raises an :class:`ExceptionIncorrectKwargs`. It also handles special
    cases for lists and numeric ranges, which should be provided as tuples of (min, max) or (min, 'inf'). Lists are
    checked to ensure all items are in the options list, and numeric values are checked against the provided ranges.
    If the value is valid, it returns the value. If the key is not found and ignore_missing_options is True, it will
    not raise an exception but will warn the user and return None. It is recommended to keep ignore_missing_options as False
    to ensure that all keyword arguments are provided and valid.
    This function is primarily used to validate keyword arguments during the initialization of class instances.
    When options contain ANY, they are not checked for validity, and the function will return the value as is.
    When options contain OPTIONAL, the function will not raise an exception if the key is not found,
    however it will validate the value if it is present.

    Args:
        dict_ (dict): The dictionary containing the key-value pairs to check.
        key_name (Hashable): The key to look for in the dictionary.
        options (List[Any]): A list of valid options for the value associated with the key.
        ignore_missing_options (Optional[bool]): If True, will not raise an exception but will warn the user and return None.
    """
    get_value = dict_.get(key_name, None)
    is_ANY = True if "ANY" in options else False
    is_OPTIONAL = True if "OPTIONAL" in options else False
    if get_value is None and not is_OPTIONAL:
        raise ExceptionIncorrectKwargs(
            key_name=key_name,
            get_value=get_value,
            options=options,
            special_case=False,
            ignore_missing_options=ignore_missing_options,
        )
    if is_ANY:
        return get_value
    if is_OPTIONAL and get_value is None:
        return get_value
    if isinstance(get_value, list):
        if any([item not in options for item in get_value]):
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
                if isinstance(get_value, tuple):
                    min_get_value, max_get_value = get_value
                    if (
                        min_value <= min_get_value <= max_value
                        and min_value <= max_get_value <= max_value
                    ):
                        return get_value
                else:
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
            special_case=False,
            ignore_missing_options=ignore_missing_options,
        )
    return get_value


class ExceptionIncorrectKwargs(Exception):
    """
    Custom exception for missing keyword arguments during initialization of class instance.
    Used in check_and_return_value(dict_, key_name, options). Should provide a message indicating
    the possible options for the user to choose from and what they entered.
    """

    def __init__(
        self,
        key_name: Hashable,
        get_value: Hashable,
        options: List[Any],
        special_case: Optional[str] = False,
        ignore_missing_options: Optional[bool] = False,
    ) -> None:
        """
        Initializes the ExceptionIncorrectKwargs with a message indicating the missing or incorrect keyword argument.
        If the keyword argument is not provided, it will raise an exception with a message indicating the options available.
        If the keyword argument is provided but not valid, it will raise an exception with a message indicating the options available.
        if ignore_missing_options is True, it will not raise an exception but will warn the user and return None.
        This is not recommended except for testing new features or using only partial parts of whatever class is
        being initialized. This function is primarily used by :func:`check_and_return_value` to validate keyword arguments

        Args:
            key_name (Hashable): The name of the keyword argument that is missing or incorrect.
            get_value (Hashable): The value of the keyword argument that was provided.
            options (List[Any]): The list of valid options for the keyword argument.
            special_case (Optional[str]): A special case for the keyword argument, such as "numeric" or "list".
                                            In such cases valid values are denoted as lower and upper bounds for numeric values
                                            or a list of valid options for list values.
            ignore_missing_options (Optional[bool]): If True, will not raise an exception but will warn the user and return None.

        """
        self.key_name = key_name
        self.get_value = get_value
        self.options = options
        if get_value is None:
            message = f"The keyword argument '{key_name}' was not provided. The options are: {options}"
        elif special_case == "numeric":
            message = f"The keyword argument '{key_name}' was provided with the value '{get_value}' but it must be between the min and max of: {options}"
        elif special_case == "list":
            get_values_not_in_options = set(
                [item for item in get_value if item not in options]
            )
            indices_in_get_value = [get_value.index(g) for g in get_values_not_in_options]
            message = (
                f"The keyword argument '{key_name}' was provided with the values in a list: '{get_values_not_in_options}' at positions {indices_in_get_value}"
                f" but they are not valid options. The options for the elements are: {options}"
            )
        else:
            message = f"The keyword argument '{key_name}' was provided with the value '{get_value}', but it is not a valid option. The options are: {options}"
        if ignore_missing_options:
            message += f" Ignoring missing options: {ignore_missing_options}"
            warn(message)
            return None

        super().__init__(message)


class SpecialTypeError(TypeError):
    """
    Custom TypeError which is raised when a function does not receive the expected arguments.
    This is used specifically when :func:`requires_loaded_files` decorator is used to load necessary files and
    insert them into the function arguments. These arguments are default None, yet are necesssary for the function to run.

    Thus this exception is raised when the function is called without the necessary arguments, but only occurs in the body
    of the function.
    """

    def __init__(self, message: str, missing_arguments: list[str]) -> None:
        self.missing_arguments = missing_arguments
        full_message = (
            f"{message}. Missing required arguments: {', '.join(self.missing_arguments)}"
        )
        super().__init__(full_message)
