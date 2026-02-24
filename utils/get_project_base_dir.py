from pathlib import Path

from errors import InvalidProjectError
from get_user_path import get_user_path


def get_project_base_dir() -> Path:
    path = get_user_path()
    while not (path / "project.ini").exists():
        if path.parent == path:
            raise InvalidProjectError(
                "No project.ini found in the current directory or its parents."
            )
        path = path.parent

    return path
