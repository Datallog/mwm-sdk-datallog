import json
import os
from argparse import Namespace
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import sleep

import requests
from conteiner import (
    conteiner_build,
    conteiner_check_if_image_exists,
    conteiner_generate_hash,
    conteiner_install_packages,
)
from create_zip_with_metadata import create_zip_with_metadata
from errors import DatallogError, LoginRequiredError, NetworkError, UnableToCreateDeployError
from get_deploy_base_dir import get_deploy_base_dir
from get_deploy_env import get_deploy_env
from halo import Halo  # type: ignore
from logger import Logger
from parser_deploy_ini import parse_deploy_ini
from token_manager import retrieve_token
from variables import datallog_url
from settings import load_settings


logger = Logger(__name__)


def push(args: Namespace) -> None:
    spinner = None
    try:
        settings = load_settings()
        token = retrieve_token()
        if not token:
            logger.error("You are not logged in. Please log in first with `datallog login`.")
            raise LoginRequiredError(
                "You are not logged in. Please log in first with `datallog login`."
            )

        logger.info(f"cwd: {os.environ.get("DATALLOG_CURRENT_PATH", os.getcwd())}")
        logger.info("Deploy with the following parameters:")
        spinner = Halo(text="Loading deploy", spinner="dots")
        spinner.start()  # type: ignore
        deploy_path = get_deploy_base_dir()
        logger.info(f"Deployment Base Directory: {deploy_path}")
        logger.info("Parsing application name...")

        deploy_ini = parse_deploy_ini(deploy_path / "deploy.ini")

        logger.info("Parsed deploy.ini successfully.")
        logger.info("Checking if Docker image exists...")

        runtime = deploy_ini.get("deploy", "runtime")
        name = deploy_ini.get("deploy", "name")
        region = deploy_ini.get("deploy", "region")

        spinner.succeed("Deploy parameters loaded successfully")  # type: ignore
        spinner.start(text="Checking Docker image")  # type: ignore
        conteiner_status = conteiner_check_if_image_exists(settings=settings, runtime_image=runtime)
        if conteiner_status != "Yes":
            if conteiner_status == "Outdated":
                spinner.fail("Docker image is outdated")  # type: ignore
            else:
                spinner.fail("Docker image does not exist") # type: ignore
            spinner.start(text="Building Docker image")  # type: ignore
            logger.warning("Docker image does not exist. Building the image...")
            conteiner_build(settings, runtime)
            spinner.succeed("Docker image built successfully")  # type: ignore
            logger.info("Docker image built successfully.")
        else:
            spinner.succeed("Runtime Docker image exists")  # type: ignore
            logger.info("Docker image exists.")

        env_path = get_deploy_env(deploy_path)
        logger.info(f"Environment Path: {env_path}")

        spinner.start(text="Installing packages")  # type: ignore

        conteiner_install_packages(
            settings=settings,
            requirements_file=deploy_path / "requirements.txt",
            runtime_image=runtime,
            env_dir=env_path,
        )
        spinner.succeed("Packages installed successfully")  # type: ignore
        spinner.start(text="Generating deploy hash")  # type: ignore
        (requirement_hash, app_hash) = conteiner_generate_hash(
            settings=settings,
            runtime_image=runtime,
            env_dir=env_path,
            deploy_dir=deploy_path,
        )
        spinner.succeed("Deploy hash generated successfully")  # type: ignore
        spinner.start(text="Checking current deploy hashes")  # type: ignore
        response_hash = requests.post(
            f"{datallog_url}/api/sdk/consult-hashes",
            json={
                "deploy_name": name,
                "applications_hash": app_hash,
                "requirements_hash": requirement_hash,
            },
            headers=token,
        )
        spinner.succeed("Deploy hashes checked successfully")  # type: ignore

        if response_hash.status_code == 404:
            logger.info(
                json.dumps(
                    {
                        "docker_version": runtime,
                        "name": name,
                        "region": region,
                    }
                )
            )
            logger.info("Creating new deploy as it does not exist.")
            spinner.start(text="Creating new deploy")  # type: ignore
            response_create_app = requests.post(
                f"{datallog_url}/api/sdk/create-deploy",
                json={
                    "docker_version": runtime,
                    "name": name,
                    "region": region,
                },
                headers=token,
            )
            if response_create_app.status_code != 200:
                create_error_message = response_create_app.json().get("message", "Unable to create a new deploy")
                raise UnableToCreateDeployError(
                    create_error_message
                )
            logger.info(f"Response from create deploy: {response_create_app.status_code}")
            logger.info(f"Created deploy: {response_create_app.json()}")
            spinner.succeed("New deploy created successfully")  # type: ignore

        elif not response_hash.ok:
            if (
                "application/json"
                in response_hash.headers.get("Content-Type", "").lower()
            ):
                error_message = response_hash.json().get("detail", "Unknown error")
                if "Invalid token" in error_message:
                    raise LoginRequiredError(
                        "Your token is invalid. Please log in first with `datallog login`."
                    )
            raise NetworkError("Failed to check deploy hashes")

        response_hash_json = response_hash.json()
        logger.info(response_hash_json)

        send_requirements = True
        send_apps = True

        requirements_build_id = None
        applications_build_id = None

        if response_hash_json.get("req_build", {'exists': False})["exists"]:
            send_requirements = False
            requirements_build_id = response_hash_json["req_build"]["id"]

        if response_hash_json.get("app_build", {'exists': False})["exists"]:
            send_apps = False
            applications_build_id = response_hash_json["app_build"]["id"]

        if send_requirements:
            spinner.start(text="Uploading requirements")  # type: ignore

            response_presinged_requirements = requests.get(
                f"{datallog_url}/api/sdk/get-deploy-requirements-presigned-url",
                params={
                    "deploy_name": name,
                },
                headers=token,
            )
            requirement_file = deploy_path / "requirements.txt"

            if not response_presinged_requirements.ok:
                raise Exception(
                    f"Failed to get presigned URL for requirements: {response_presinged_requirements.text}"
                )
            with open(requirement_file, "r") as f:
                logger.info(f"Requirements file content: {f.read()}")
            presigned_url = response_presinged_requirements.json()
            logger.info(f"Uploading requirements to {presigned_url}")
            with open(requirement_file, "rb") as f:
                # content-type text/plain
                response = requests.put(
                    presigned_url,
                    headers={
                        "Content-Type": "text/plain",
                    },
                    data=f,
                )
                logger.info(f"Response from S3 upload: {response.text}")
                response.raise_for_status()  # Raise an error for bad responses

            logger.info("Requirements uploaded successfully.")
            logger.info(
                json.dumps(
                    {
                        "deploy_name": name,
                        "url_s3": presigned_url,
                        "file_hash": requirement_hash,
                    },
                    indent=4,
                )
            )
            response_notify_requirements_upload = requests.post(
                f"{datallog_url}/api/sdk/confirm-requirements-upload",
                json={
                    "deploy_name": name,
                    "url_s3": presigned_url,
                    "file_hash": requirement_hash,
                },
                headers=token,
            )
            logger.info(response_notify_requirements_upload.text)
            logger.info(str(response_notify_requirements_upload.status_code))
            if response_notify_requirements_upload.status_code != 201:
                raise Exception(
                    f"Failed to confirm requirements upload: {response_notify_requirements_upload.text}"
                )
            spinner.succeed(text="Requirements uploaded successfully")  # type: ignore

            requirements_build_id = response_notify_requirements_upload.json().get(
                "requirements_build_id"
            )

        if not requirements_build_id:
            raise DatallogError(
                "Something went wrong, requirements build ID is missing."
            )

        logger.info(f"Requirements build ID: {requirements_build_id}")
        status = "BUILDING"
        spinner.start(text="Waiting for requirements image build to finish")  # type: ignore
        while status == "BUILDING":
            response_requirements_build_status = requests.get(
                f"{datallog_url}/api/sdk/requirements-build-status/{requirements_build_id}",
                headers=token,
            )
            requirements_build_status_json = response_requirements_build_status.json()
            logger.info(
                f"Requirements build status response: {requirements_build_status_json}"
            )
            status = requirements_build_status_json.get("status", "BUILDING")
            logger.info(f"Requirements build status: {status}")
            if status == "BUILDING":
                sleep(5)  # Wait for 5 seconds before checking again
        spinner.succeed("Requirements image build finished")  # type: ignore

        if send_apps:
            spinner.start(text="Generating applications bundle")  # type: ignore

            with NamedTemporaryFile() as temp_file:
                create_zip_with_metadata(
                    deploy_path,
                    output_zip_filename=Path(temp_file.name),
                )
                spinner.succeed("Applications bundle created successfully")  # type: ignore

                temp_file.seek(0)
                response_presinged_apps = requests.get(
                    f"{datallog_url}/api/sdk/get-deploy-applications-presigned-url",
                    params={
                        "deploy_name": name,
                    },
                    headers=token,
                )
                if not response_presinged_apps.ok:
                    raise Exception(
                        f"Failed to get presigned URL for applications: {response_presinged_apps.text}"
                    )

                presigned_url = response_presinged_apps.json()
                spinner.start(text="Uploading applications")  # type: ignore
                response = requests.put(
                    presigned_url,
                    headers={
                        "Content-Type": "application/zip",
                    },
                    data=temp_file,
                )
                logger.info(f"Response from S3 upload: {response.text}")
                response.raise_for_status()
                logger.info("Applications uploaded successfully.")

            logger.info(
                json.dumps(
                    {
                        "deploy_name": name,
                        "url_s3": presigned_url,
                        "file_hash": app_hash,
                        "requirements_build_identifier": requirements_build_id,
                    },
                    indent=4,
                )
            )
            logger.info("Waiting for applications build to finish...")
            response_notify_apps_upload = requests.post(
                f"{datallog_url}/api/sdk/confirm-applications-upload",
                json={
                    "deploy_name": name,
                    "url_s3": presigned_url,
                    "file_hash": app_hash,
                    "requirements_build_identifier": requirements_build_id,
                },
                headers=token,
            )

            logger.info(response_notify_apps_upload.text)
            logger.info(str(response_notify_apps_upload.status_code))
            spinner.succeed(text="Applications uploaded successfully")  # type: ignore

            if response_notify_apps_upload.status_code != 201:
                raise Exception(
                    f"Failed to confirm applications upload: {response_notify_apps_upload.text}"
                )
            logger.info("Applications upload confirmed successfully.")
            applications_build_id = response_notify_apps_upload.json().get(
                "applications_build_id"
            )
        logger.info(f"Applications build ID: {applications_build_id}")
        status = "BUILDING"
        spinner.start(text="Waiting for applications image build to finish")  # type: ignore

        while status == "BUILDING":
            response_apps_build_status = requests.get(
                f"{datallog_url}/api/sdk/applications-build-status/{applications_build_id}",
                headers=token,
            )
            apps_build_status_json = response_apps_build_status.json()
            logger.info(
                f"Applications build status response: {apps_build_status_json}"
            )
            status = apps_build_status_json.get("status", "BUILDING")
            logger.info(f"Applications build status: {status}")
            if status == "BUILDING":
                sleep(5)
        spinner.succeed("Applications image build finished")  # type: ignore
    
    except DatallogError as e:
        if spinner:
            spinner.fail(f"Error: {e}")  # type: ignore
        else:
            logger.error(f"Error: {e}")
            print(f"\033[91m{e.message}\033[0m")