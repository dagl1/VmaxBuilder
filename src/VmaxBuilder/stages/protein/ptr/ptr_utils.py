from typing import Any


def _normalize_sample_label(value: Any) -> str:
    """Generated: validation needed.

    Description:
        Normalize sample/tissue labels for robust matching across expression,
        PTR, and explicit tissue-map configuration.

    Args:
        value (Any): Raw label value.

    Returns:
        str: Normalized label (trimmed, lower-case, optional ``_ptr`` suffix removed).
    """
    text = str(value).strip().lower()
    if text.endswith("_ptr"):
        text = text[: -len("_ptr")]
    return text


def is_valid_int(val):
    try:
        return float(val).is_integer()
    except (ValueError, TypeError):
        return False
