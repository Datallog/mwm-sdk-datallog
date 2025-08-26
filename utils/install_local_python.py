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


def get_python_executable(python_version: str) -> Path:
    """
    Finds and sets a suitable Python executable based on pyenv.
    This function will install pyenv and the required Python version if they are not found.
    """

    if not is_command_available("pyenv"):
        raise UnableToFindPythonExecutableError(
            f"Failed to find 'pyenv' command. Please ensure pyenv is installed and available in your PATH."
        )

    logger.info(
        f"Searching for the latest patch version of Python {python_version}..."
    )

    # Using shell for grep to simplify the command
    list_cmd = (
        f"pyenv install --list | grep -E '^\\s*{python_version}\\.[0-9]+$' | tail -n 1"
    )

    latest_version, _, retcode = run_command(list_cmd, shell=True)

    if retcode != 0 or not latest_version:
        logger.error(
            f"Could not find any installable version for Python {python_version}"
        )
        raise UnableToFindPythonExecutableError(
            f"Failed to find any installable version for Python {python_version}."
        )

    logger.info(f"Latest available version is {latest_version}.")

    # Check if this version is already installed
    installed_versions, _, _ = run_command(["pyenv", "versions", "--bare"])
    if installed_versions and latest_version not in installed_versions.split("\n"):
        logger.info(
            f"Python {latest_version} is not installed. Installing now (this may take a while)..."
        )
        _, stderr, retcode = run_command(["pyenv", "install", latest_version])
        if retcode != 0:
            logger.error(f"Failed to install Python {latest_version}. Error: {stderr}")
            raise UnableToFindPythonExecutableError(
                f"Failed to install Python {latest_version}. Error: {stderr}"
            )

        logger.info(f"Successfully installed Python {latest_version}.")

    # 5. Get the executable path from pyenv
    logger.info(f"Resolving path for Python executable alias ...")

    pyenv_root_path = Path(os.getenv("PYENV_ROOT", str(Path.home() / ".pyenv")))
    if not pyenv_root_path.exists():
        logger.error(
            f"PYENV_ROOT path '{pyenv_root_path}' does not exist. Please ensure pyenv is installed correctly."
        )
        raise UnableToFindPythonExecutableError(
            f"PYENV_ROOT path '{pyenv_root_path}' does not exist."
        )

    found_python_path = pyenv_root_path / "versions" / latest_version / "bin" / "python"

    if not found_python_path.exists():
        logger.error(
            f"Could not find Python executable at '{found_python_path}'. Please ensure the version is installed correctly."
        )
        raise UnableToFindPythonExecutableError(
            f"Failed to find Python executable at '{found_python_path}'."
        )

    if retcode != 0:
        logger.error(
            f"Failed to resolve Python executable path for version '{latest_version}'."
        )
        raise UnableToFindPythonExecutableError(
            f"Failed to resolve Python executable path for version '{latest_version}'."
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
            subprocess.run(
                [python_executable, "-m", "venv", str(venv_path)],
                check=True,
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
        installed_requiments_process = subprocess.run(
            [python_executable, "-m", "pip", "freeze", "--local"],
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
            [python_executable, "-m", "pip", "install", "-r", str(requirements_file)],
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
        subprocess.run(
            [str(python_executable), "-m", "pip", "install"] + packages,
            check=True,
            cwd=project_dir,
        )
        logger.info("Packages installed successfully.")

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install packages {packages}. Error: {e.stderr}")
        raise UnableToInstallPackagesError(
            f"Failed to install packages {packages}. Error: {e.stderr}"
        )
