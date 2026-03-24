import json
import os
import ast
from argparse import Namespace
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import sleep
import requests
from container import (
    Dict,
    container_build,
    container_check_if_image_exists,
    container_generate_hash,
    container_install_packages
)
from errors import (
    DatallogError,
    LoginRequiredError,
    NetworkError,
    PlanExpiredError,
    UnableToCreateProjectError,
)
from get_project_base_dir import get_project_base_dir
from get_project_env import get_project_env
from halo import Halo  # type: ignore
from spinner import Spinner
from logger import Logger
from parser_project_ini import parse_project_ini
from token_manager import retrieve_token, retrieve_user_info
from .login import login as login_cmd
from variables import datallog_url
from settings import load_settings


logger = Logger(__name__)


def push(args: Namespace) -> None:
    spinner = None
    try:
        settings = load_settings()
        project_path = get_project_base_dir()
        token = retrieve_token(project_path)
        if not token:
            print("\n\033[93m[WARNING]\033[0m You are not logged in.")
            confirm = input("Would you like to log in now? (Y/n): ").strip().lower()
            if confirm == "n":
                raise LoginRequiredError("You must be logged in to push a project.")
            
            # Use force_login and project_path to trigger local login
            setattr(args, "force_login", True)
            setattr(args, "project_path", project_path)
            from .login import login as login_cmd
            login_cmd(args)
            token = retrieve_token(project_path)
            if not token:
                raise LoginRequiredError("Login required to continue.")

        logger.info(f"cwd: {os.environ.get('DATALLOG_CURRENT_PATH', os.getcwd())}")
        project_ini = parse_project_ini(project_path / "project.ini")
        
        # Check if it's the first push for this project using project.ini
        last_pushed_by = None
        if project_ini.has_option("project", "last_pushed_by"):
            last_pushed_by = project_ini.get("project", "last_pushed_by")

        if not last_pushed_by:
            user_info = retrieve_user_info(project_path)
            
            # If user_info is missing locally but we have a token, fetch it from backend once
            if not user_info and token:
                try:
                    from subcommands.login import verify_token_url
                    resp = requests.post(verify_token_url, headers=token, timeout=5)
                    if resp.status_code == 200:
                        data = resp.json()
                        user_info = {"email": data.get("email"), "username": data.get("username")}
                        from token_manager import save_user_info
                        save_user_info(user_info, project_path)
                except Exception:
                    pass

            account_display = "Verificação pendente (verifique sua conexão ou refaça o login)"
            current_email = ""
            if user_info:
                current_email = user_info.get("email", "")
                username = user_info.get("username", "")
                if current_email and username:
                    account_display = f"{username} ({current_email})"
                elif current_email:
                    account_display = current_email
            
            print(f"\n\033[94m[NOTICE]\033[0m No previous push recorded for this project.")
            print(f"\033[94m[NOTICE]\033[0m Current logged in account: \033[1;32m{account_display}\033[0m")
            confirm = input("\nAre you sure you want to push to this account? (Y/n): ").strip().lower()
            if confirm == "n":
                print("Switching account...")
                # Set force login and project path to skip redundant confirmation 
                # and save token locally
                setattr(args, "force_login", True)
                setattr(args, "project_path", project_path)
                from .login import login as login_cmd
                login_cmd(args)
                token = retrieve_token(project_path) # Refresh token after login
                if not token:
                    raise LoginRequiredError("Login required to continue.")
                
                # Refresh user info after login
                user_info = retrieve_user_info(project_path)
                if user_info:
                    current_email = user_info.get("email", "")
            else:
                # User said YES (or default). Lock this account to this project.
                # This prevents global account switches from affecting this project.
                if token and user_info:
                    from token_manager import save_token, save_user_info, encode_token
                    # authorization and x-api-key are in the token dict
                    auth = token.get("Authorization", "")
                    x_api = token.get("x-api-key", "")
                    if auth and x_api:
                        save_token(encode_token(auth, x_api), project_path)
                        save_user_info(user_info, project_path)
                        current_email = user_info.get("email", "")

            # Save the account to project.ini so we don't ask again
            if current_email:
                project_ini.set("project", "last_pushed_by", current_email)
                with open(project_path / "project.ini", "w") as f:
                    project_ini.write(f)

        spinner = Spinner("Loading project...")
        spinner.start()  # type: ignore

        logger.info(f"Project Base Directory: {project_path}")
        logger.info("Parsing application name...")

        logger.info("Parsed project.ini successfully.")
        logger.info("Checking if Docker image exists...")

        runtime = project_ini.get("project", "runtime")
        name = project_ini.get("project", "name")
        region = project_ini.get("project", "region")

        spinner.succeed("Project parameters loaded successfully")
        
        if runtime == "custom":
            # For custom projects, we expect the user to have customized their .datallog.Dockerfile.
            # We don't build a datallog-runtime base image.
            base_image = "python:3.10-alpine" # Default fallback if we need to auto-generate
            logger.info("Custom environment detected, skipping datallog-runtime validation/build.")
        else:
            # Determine the base Docker image
            # The runtime string relates to local 'datallog-runtime-{runtime}' images built from .datallog/runtimes
            base_image = f"datallog-runtime-{runtime}"
            
            # Check if runtime image exists and is up to date, build if not
            image_status = container_check_if_image_exists(settings, runtime)
            if image_status != "Yes":
                logger.info(f"Building local runtime image {base_image}...")
                spinner.start(text=f"Building local datallog runtime {base_image}")
                container_build(settings, runtime)
                spinner.succeed(f"Local runtime {base_image} built successfully")
        
        env_path = get_project_env(project_path)
        logger.info(f"Environment Path: {env_path}")

        spinner.start(text="Generating project hash")
        import uuid
        unified_hash = uuid.uuid4().hex
        spinner.succeed("Project hash generated successfully")
        
        # Verify and fetch registry temporary credentials from backend
        ecr_response = requests.get(
            f"{datallog_url}/api/sdk/v4/get-ecr-credentials",
            params={"deploy_name": name},
            headers=token
        )

        if ecr_response.status_code == 404:
            # Project does not exist, let's create it
            logger.info("Creating new project as it does not exist.")
            spinner.start(text="Creating new project")
            response_create_app = requests.post(
                f"{datallog_url}/api/sdk/create-project",
                json={
                    "docker_version": runtime,
                    "name": name,
                    "region": region,
                },
                headers=token,
            )
            if response_create_app.status_code != 200:
                raise UnableToCreateProjectError(response_create_app.json().get("message", "Unable to create a new project"))
            
            spinner.succeed("New project created successfully")
            ecr_response = requests.get(
                f"{datallog_url}/api/sdk/v4/get-ecr-credentials",
                params={"deploy_name": name},
                headers=token
            )

        if not ecr_response.ok:
            error_msg = ecr_response.json().get("message", "Failed to retrieve registry credentials")
            raise NetworkError(f"Failed to get credentials: {error_msg}")

        ecr_data = ecr_response.json()
        credentials = ecr_data["credentials"]
        registry_url = ecr_data["registry_url"]
        repository_uri = ecr_data["repository_uri"]

        # Log into Docker manually since STS gives limited duration tokens
        
        docker_username = ecr_data.get("docker_username")
        docker_password = ecr_data.get("docker_password")
        
        if not docker_username or not docker_password:
             raise Exception("Backend did not return Docker registry credentials.")

        import subprocess
        login_process = subprocess.run(
            ['docker', 'login', '--username', docker_username, '--password-stdin', registry_url],
            input=docker_password.encode('utf-8'),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if login_process.returncode != 0:
             raise Exception(f"Failed to authenticate Docker: {login_process.stderr.decode('utf-8')}")

        spinner.start(text="Building project Docker image locally")
        
        image_tag = f"{repository_uri}:{unified_hash}"
        
        dockerfile_path = project_path / "datallog.Dockerfile"
        created_temp_dockerfile = False
        
        if not dockerfile_path.exists():
            dockerfile_content = f"""
FROM {base_image}
WORKDIR /project
COPY requirements.txt /project/requirements.txt
RUN pip install --no-cache-dir -r /project/requirements.txt
COPY . /project
"""
            with open(dockerfile_path, "w") as f:
                f.write(dockerfile_content)
            created_temp_dockerfile = True
        else:
            logger.info("Using custom user-provided datallog.Dockerfile")

        build_process = subprocess.run(
            ['docker', 'build', '-t', image_tag, '-f', "datallog.Dockerfile", "."],
            cwd=str(project_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        if created_temp_dockerfile and dockerfile_path.exists():
            dockerfile_path.unlink()

        if build_process.returncode != 0:
            raise Exception(f"Failed to build Docker image: {build_process.stderr.decode('utf-8')}")
        
        spinner.succeed("Local Docker build completed")

        spinner.start(text="Extracting project applications and requirements")
        try:
            from container import container_generate_build
            build_data = container_generate_build(
                settings, 
                image_tag, 
                project_path, 
                env_path,
                is_custom_image=True
            )
            automations_list = build_data.get("automations", [])
            spinner.succeed(f"Found {len(automations_list)} applications")
        except Exception as e:
            # Check log level to decide if we show full internal traceback or just the error
            if os.getenv("DATALLOG_LOG_LEVEL", "INFO").upper() == "DEBUG":
                import traceback
                print(traceback.format_exc())
            
            spinner.fail("Failed to extract applications")
            
            error_str = str(e)
            relevant_lines = [l for l in error_str.splitlines() if l.strip()]
            main_error = relevant_lines[-1] if relevant_lines else error_str

            print(f"\n\033[91m{'='*70}\033[0m")
            print(f"\033[1;91mError Detected:\033[0m \033[94m{main_error}\033[0m")
            print(f"\033[91m{'='*70}\033[0m")
            print(f"\n{error_str}")
            print(f"\033[91m{'='*70}\033[0m\n")
            return  # Stop the push as further steps would likely fail and create confusing logs

        spinner.start(text="Pushing project to cloud")
        push_process = subprocess.run(
            ['docker', 'push', image_tag],
            cwd=str(project_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if push_process.returncode != 0:
             raise Exception(f"Failed to push to cloud: {push_process.stderr.decode('utf-8')}")
             
        spinner.succeed("Project successfully pushed to cloud")


        requirements_content = ""
        req_path = project_path / "requirements.txt"
        if req_path.exists():
            with open(req_path, 'r', encoding='utf-8') as f:
                requirements_content = f.read()
        spinner.start(text="Notifying MWM to trigger final infrastructure setup")
        
        notify_response = requests.post(
            f"{datallog_url}/api/sdk/v4/notify-user-push",
            json={
                "deploy_name": name,
                "file_hash": unified_hash,
                "automations": automations_list,
                "requirements_txt": requirements_content
            },
            headers=token,
        )

        if notify_response.status_code not in (200, 201):
             try:
                 error_msg = notify_response.json().get("message", notify_response.text)
             except json.decoder.JSONDecodeError:
                 error_msg = f"Server returned {notify_response.status_code}: {notify_response.text[:200]}"
             raise Exception(f"Failed to notify backend: {error_msg}")
             
        build_id = notify_response.json().get("build_id")
        if not build_id:
            logger.warning("No build_id returned; proceeding without polling.")
            spinner.succeed("Project pushed successfully, but unable to track build status.", boxed=True)
        else:
            spinner.succeed("Backend notified successfully")
            spinner.start(text="Waiting for final infrastructure setup to complete (this may take a minute)")
            
            import time
            while True:
                status_response = requests.get(
                    f"{datallog_url}/api/sdk/automation-build-status/{build_id}",
                    headers=token
                )
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    status_text = status_data.get("status", "UNKNOWN")
                    
                    if status_text in ("SUCCESS", "COMPLETED"):
                        spinner.succeed("Final infrastructure setup completed successfully", boxed=True)
                        break
                    elif status_text in ("FAILED", "ERROR"):
                        error_message = status_data.get("message", "Unknown error")
                        raise Exception(f"Final setup failed on cloud infrastructure: {error_message}")
                elif status_response.status_code == 404:
                    raise Exception("Build ID not found on backend.")
                
                time.sleep(5)
    except DatallogError as e:
        if spinner:
            spinner.fail(f"Error: {e}")  # type: ignore
        else:
            logger.error(f"Error: {e}")
            print(f"\033[91m{e.message}\033[0m")
    except KeyboardInterrupt:
        if spinner:
            spinner.fail("Operation cancelled by user (Ctrl+C)")
        else:
            logger.error("Operation cancelled by user")
            print("\033[91mOperation cancelled by user (Ctrl+C)\033[0m")
    except Exception as e:
        if spinner:
            spinner.fail(f"Unexpected error: {str(e)}", boxed=True)
        else:
            logger.error("Unexpected error")
            print(f"\033[91mUnexpected error: {str(e)}\033[0m")