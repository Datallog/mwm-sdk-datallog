import os
from typing import List
import zipfile
import json
from pathlib import Path
from errors import EmptyDeployDirError, UnableToBundleAppError
from container import (
    container_build,
    container_check_if_image_exists,
    container_generete_build,
    container_install_packages,
)
from parser_deploy_ini import parse_deploy_ini
from get_deploy_env import get_deploy_env
from logger import Logger
from settings import load_settings
logger = Logger(__name__)

def create_zip_with_metadata(deploy_path: Path, output_zip_filename: Path) -> None:
    """
    Creates a ZIP file from a source directory and includes a metadata.json file.

    Args:
        source_dir (str): The path to the directory to be zipped.
        output_zip_filename (str, optional): The desired name for the output ZIP file.
                                            If None, it defaults to 'source_dir_name.zip'.
    """

    settings = load_settings()

    logger.info(f"Source directory: {deploy_path.absolute()}")
    logger.info(f"Output ZIP file: {Path(output_zip_filename).absolute()}")

    files_to_zip: List[Path] = []
    # Walk through the source directory to find all files
    for root, _, files in os.walk(deploy_path.absolute()):
        relative_path = Path(root).relative_to(deploy_path)
        # ignore env
        parts = relative_path.parts
        if len(parts) > 0:
            if "__pycache__" in parts:
                continue
            if parts[0] == "env":
                continue

        logger.info(f"Processing directory: {relative_path}")
        for file in files:

            file_path = Path(root) / file
            files_to_zip.append(file_path)

    if not files_to_zip:
        raise EmptyDeployDirError(
            f"Warning: No files found in '{deploy_path.absolute()}'."
        )

    # Generate metadata
    # The file_count here is the number of actual files from the directory

    deploy_ini = parse_deploy_ini(deploy_path / "deploy.ini")
    runtime = deploy_ini.get("deploy", "runtime")
    container_status = container_check_if_image_exists(settings, runtime) 
    if  container_status != "Yes":
        logger.info(f"Docker image status {container_status}. Building the image...")
        container_build(settings, runtime)
    else:
        logger.info("Docker image exists.")
    env_path = get_deploy_env(deploy_path)
    logger.info(f"Environment Path: {env_path}")
    container_install_packages(
        settings=settings,
        requirements_file=deploy_path / "requirements.txt",
        runtime_image=runtime,
        env_dir=env_path,
    )

    metadata_content = container_generete_build(
        settings=settings,
        runtime_image=runtime, deploy_dir=deploy_path, env_dir=env_path
    )
    metadata_json_str = json.dumps(metadata_content, indent=4)
    logger.info("Metadata content generated successfully.")
    logger.info(f"Metadata content:\n{metadata_json_str}")
    metadata_filename = "build.json"
    deploy_dir = Path("deploy")
    try:
        with zipfile.ZipFile(output_zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
            # Add all files from the source directory
            for file_path in files_to_zip:
                # arcname is the name of the file within the archive
                # This preserves the directory structure relative to source_dir
                arcname = deploy_dir / file_path.relative_to(deploy_path)
                zipf.write(file_path, arcname=arcname)
                # print(f"  Adding file: {arcname}")

            # Add the metadata.json file to the root of the archive
            zipf.writestr(metadata_filename, metadata_json_str)
            logger.info(f"  Adding metadata: {metadata_filename}")

        logger.info(
            f"\nSuccessfully created '{output_zip_filename}' with {len(files_to_zip)} file(s) and '{metadata_filename}'."
        )

    except FileNotFoundError as e:
        raise UnableToBundleAppError(
            f"One of the files was not found. This can happen if files are moved/deleted during the operation."
        ) from e
    except PermissionError as e:
        raise UnableToBundleAppError(
            f"Permission denied. Check if you have write permissions for '{output_zip_filename}' or read permissions for files in '{deploy_path}'."
        ) from e
    except Exception as e:
        raise UnableToBundleAppError(f"An unexpected error occurred: {e}") from e
