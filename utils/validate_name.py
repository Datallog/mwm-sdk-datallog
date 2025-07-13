import re


def validate_name(name: str) -> bool:
    """
    Validates a name based on specific criteria:
    - Must start with a letter (a-z, A-Z)
    - Can contain letters, digits (0-9), underscores (_), and hyphens (-)
    - Must be between 3 and 50 characters long

    Args:
        name (str): The name to validate.

    Returns:
        bool: True if the name is valid, False otherwise.
    """
    pattern = r"^[a-zA-Z][a-zA-Z0-9_-]{2,49}$"
    return bool(re.match(pattern, name))