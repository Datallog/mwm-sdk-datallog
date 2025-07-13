

import os
from pathlib import Path

from errors import InvalidAppError


def get_user_path() -> Path:
    current_path = os.environ.get("DATALLOG_CURRENT_PATH", None)
    if current_path is None:
        raise InvalidAppError(
            "Environment variable 'DATALLOG_CURRENT_PATH' is not set. Reinstall the SDK."
        )

    return Path(current_path).absolute()
    