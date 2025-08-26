import configparser
from pathlib import Path


def parse_project_ini(file_path: Path) -> configparser.ConfigParser:
    """
    Parse the project.ini file and return a ConfigParser object.

    Args:
        file_path (Path): Path to the project.ini file.

    Returns:
        configparser.ConfigParser: Parsed configuration.
    """
    config = configparser.ConfigParser()
    config.read(file_path)

    if not config.sections():
        raise ValueError(
            f"No sections found in {file_path}. Ensure the file is correctly formatted."
        )
    return config
