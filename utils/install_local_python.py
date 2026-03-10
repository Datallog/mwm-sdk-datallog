#!/usr/bin/env python3
import os
from pathlib import Path
import subprocess
from typing import List, Union
import shutil


from logger import Logger
from execution import Optional
from container import Tuple
from errors import (
    UnableToCreateVirtualEnvError,
    UnableToFindPythonExecutableError,
    UnableToInstallPackagesError,
)

logger = Logger(__name__)
UV_BIN_DIR = Path.home() / ".local" / "bin"


def run_command(
    command: Union[str, List[str]], shell: bool = False
) -> Tuple[Optional[str], str, int]:
    """
    Executes a command and returns its output, error, and exit code.
    """
    try:
        process = subprocess.run(
            command,
            shell=shell,
            capture_output=True,
            text=True,
            check=False,  # Do not raise an exception on non-zero exit codes
        )
        return process.stdout.strip(), process.stderr.strip(), process.returncode
    except FileNotFoundError:
        logger.error(f"Command not found: {command[0]}")
        return None, f"Command not found: {command[0]}", 1
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while running command '{' '.join(command)}': {e}"
        )
        return None, str(e), 1


def is_command_available(command: str) -> bool:
    """
    Checks if a command is available in the system's PATH.
    Equivalent to 'command -v'.
    """
    return shutil.which(command) is not None


def get_uv_command() -> str:
    """
    Resolves the uv executable, including the default user install location.
    """
    uv_path = shutil.which("uv")
    if uv_path:
        return uv_path

    candidate = UV_BIN_DIR / "uv"
    if candidate.exists():
        return str(candidate)

    raise UnableToFindPythonExecutableError(
        "Failed to find 'uv' command. Please ensure uv is installed and available in your PATH."
    )

def get_python_version_mapping(python_version: str) -> str:
    python_version_mapping: dict[str, str] = {
        "3.10-selenium": "3.10",
        "3.11-selenium": "3.11",
        "3.12-selenium": "3.12",
    }
    return python_version_mapping.get(python_version, python_version)

def get_python_executable(python_version: str) -> Path:
    """
    Finds and installs a suitable Python executable using uv.
    """
    python_version = get_python_version_mapping(python_version)
    uv_command = get_uv_command()

    logger.info(
        f"Searching for the latest patch version of Python {python_version}..."
    )

    logger.info(f"Installing Python {python_version} with uv if needed...")
    _, stderr, retcode = run_command([uv_command, "python", "install", python_version])
    if retcode != 0:
        logger.error(f"Failed to install Python {python_version}. Error: {stderr}")
        raise UnableToFindPythonExecutableError(
            f"Failed to install Python {python_version}. Error: {stderr}"
        )

    logger.info("Resolving path for Python executable alias ...")
    found_python_path_raw, stderr, retcode = run_command(
        [uv_command, "python", "find", python_version]
    )
    if retcode != 0 or not found_python_path_raw:
        logger.error(
            f"Failed to resolve Python executable path for version '{python_version}'. Error: {stderr}"
        )
        raise UnableToFindPythonExecutableError(
            f"Failed to resolve Python executable path for version '{python_version}'. Error: {stderr}"
        )

    found_python_path = Path(found_python_path_raw.splitlines()[0].strip())
    if not found_python_path.exists():
        logger.error(
            f"Could not find Python executable at '{found_python_path}'. Please ensure the version is installed correctly."
        )
        raise UnableToFindPythonExecutableError(
            f"Failed to find Python executable at '{found_python_path}'."
        )

    if not os.access(found_python_path, os.X_OK):
        logger.error(f"Resolved path '{found_python_path}' is not an executable.")
        raise UnableToFindPythonExecutableError(
            f"Resolved path '{found_python_path}' is not an executable."
        )

    return Path(found_python_path)


def create_local_env(project_dir: Path, python_executable: Path) -> Path:
    """
    Creates a local Python environment in the specified project directory.
    """

    # Create a virtual environment
    venv_path = project_dir / "env"
    python_bin = venv_path / "bin" / "python"

    if not python_bin.exists() and venv_path.exists():
        logger.info(f"Removing existing virtual environment at {venv_path}...")
        shutil.rmtree(venv_path)

    if not venv_path.exists():
        logger.info(f"Creating virtual environment at {venv_path}...")
        try:
            uv_command = get_uv_command()
            subprocess.run(
                [uv_command, "venv", "--python", str(python_executable), str(venv_path)],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error(
                f"Failed to create virtual environment at {venv_path}. Error: {e.stderr}"
            )
            raise UnableToCreateVirtualEnvError(
                f"Failed to create virtual environment at {venv_path}. Error: {e.stderr}"
            )

        logger.info("Virtual environment created successfully.")

    return venv_path


def install_local_packages_from_requirements(
    project_dir: Path, python_executable: Path, requirements_file: Path
) -> None:
    """
    Installs packages from a requirements file in the local Python environment.
    """

    if not requirements_file.exists():
        logger.error(
            f"Requirements file '{requirements_file}' does not exist. Cannot install packages."
        )
        return

    logger.info(f"Installing packages from {requirements_file}...")
    with open(str(requirements_file), "r") as f:
        requirements = set(f.read().strip().splitlines())

    try:
        uv_command = get_uv_command()
        installed_requiments_process = subprocess.run(
            [uv_command, "pip", "freeze", "--python", str(python_executable)],
            check=True,
            cwd=project_dir,
            capture_output=True,
            text=True,
        )

        installed_requiments_set = set(
            installed_requiments_process.stdout.strip().splitlines()
        )

    except subprocess.CalledProcessError as e:
        logger.error(
            f"Failed to check installed packages in {project_dir}. Error: {e.stderr}"
        )
        raise UnableToInstallPackagesError(
            f"Failed to check installed packages in {project_dir}. Error: {e.stderr}"
        )

    if requirements.issubset(installed_requiments_set):
        logger.info(
            f"All required packages from {requirements_file} are already installed in {project_dir}."
        )
        return

    try:
        subprocess.run(
            [
                uv_command,
                "pip",
                "install",
                "--python",
                str(python_executable),
                "-r",
                str(requirements_file),
            ],
            check=True,
            cwd=project_dir,
        )
        logger.info("Packages installed successfully.")

    except subprocess.CalledProcessError as e:
        logger.error(
            f"Failed to install packages from {requirements_file}. Error: {e.stderr}"
        )
        raise UnableToInstallPackagesError(
            f"Failed to install packages from {requirements_file}. Error: {e.stderr}"
        )


def install_local_python_packages(
    project_dir: Path, python_executable: Path, packages: List[str]
) -> None:
    """
    Installs specified packages in the local Python environment.
    """
    if not packages:
        logger.info("No packages to install.")
        return

    logger.info(f"Installing packages: {', '.join(packages)}...")

    try:
        uv_command = get_uv_command()
        subprocess.run(
            [uv_command, "pip", "install", "--python", str(python_executable)] + packages,
            check=True,
            cwd=project_dir,
        )
        logger.info("Packages installed successfully.")

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install packages {packages}. Error: {e.stderr}")
        raise UnableToInstallPackagesError(
            f"Failed to install packages {packages}. Error: {e.stderr}"
        )
