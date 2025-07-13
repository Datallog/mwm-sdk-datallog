from pathlib import Path

from errors import InvalidAppError
from get_user_path import get_user_path


def get_deploy_base_dir() -> Path:
    path = get_user_path()
    while not (path / "deploy.ini").exists():
        if path.parent == path:
            raise InvalidAppError(
                "No deploy.ini found in the current directory or its parents."
            )
        path = path.parent

    return path
