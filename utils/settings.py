import json

from errors import InvalidSettingsError
from schema import Settings
from pathlib import Path


def get_settings_path() -> Path:
    return Path.cwd() / ".." / "settings.json"


def load_settings() -> Settings:
    """
    Load settings from a JSON file and return a Pydantic model instance.
    """
    try:
        with open(get_settings_path(), "r") as file:
            data = json.load(file)
        return Settings(**data)
    except FileNotFoundError:
        return Settings()
    except json.JSONDecodeError as e:
        raise InvalidSettingsError(f"Invalid settings file: {e}") from e


def save_settings(settings: Settings) -> None:
    """
    Save settings to a JSON file.
    """
    with open(get_settings_path(), "w") as file:
        file.write(settings.model_dump_json(indent=4))
