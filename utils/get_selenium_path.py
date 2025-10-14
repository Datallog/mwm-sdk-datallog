

from pathlib import Path


def get_selenium_path() -> Path:
    """
    Get the path to the selenium driver directory.
    """

    path = Path.cwd() / ".." / "selenium-drivers"
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    return path.resolve()
