"""
Tavern verify_response_with helper functions.

Each function receives the raw requests.Response object as its first argument,
followed by any extra_kwargs declared in the YAML spec.
"""

from loguru import logger


def response_contains(response, field: str, substring: str) -> None:
    """
    Assert that a dot-delimited field in the JSON response body contains a substring.

    Example YAML usage:
        verify_response_with:
          - function: utils.tavern_helpers:response_contains
            extra_kwargs:
              field: response.text
              substring: approved

    Args:
        response: requests.Response object from Tavern
        field: Dot-separated path into the JSON body (e.g. "response.text")
        substring: Case-insensitive substring that must appear in the field value
    """
    data = response.json()
    value = data
    for key in field.split("."):
        if not isinstance(value, dict) or key not in value:
            raise AssertionError(
                f"Field '{field}' not found in response. "
                f"Missing key '{key}' in: {value}"
            )
        value = value[key]

    text = str(value).lower()
    needle = substring.lower()
    logger.info(f"Checking '{field}' contains '{substring}': value={value!r}")
    assert needle in text, (
        f"Expected '{substring}' in '{field}' but got: {value!r}"
    )
