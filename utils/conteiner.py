import json
import os
import subprocess
from pathlib import Path
import threading
from typing import IO, Any, Dict, Optional, Tuple, List, Literal
from errors import (
    CannotConnectToDockerDaemonError,
    DatallogRuntimeError,
    UnableToBuildImageError,
)
from datetime import datetime, timezone
from tempfile import NamedTemporaryFile
import sys
from logger import Logger
from schema import Settings
import re
import pytz

logger = Logger(__name__)


class StreamTee(threading.Thread):
    """
    A thread that reads from a stream (like stdout or stderr),
    prints it to a destination stream (like sys.stdout), and captures
    it in a list, all at the same time.
    """

    def __init__(
        self, source_stream: IO[str], dest_stream: IO[str], capture_list: List[str], print_output: bool = False
    ):
        super().__init__()
        self.source_stream = source_stream
        self.dest_stream = dest_stream
        self.capture_list = capture_list
        self.print_output = print_output
        self.daemon = True  # Allows main program to exit even if threads are running

    def run(self):
        """The main logic of the thread."""
        # Read from the source stream line by line until it's closed
        for line in self.source_stream:
            os.system(command='stty sane')
            if self.print_output:
                self.dest_stream.write(line)
            self.capture_list.append(line)  # Capture the line


def conteiner_exec(
    args: List[str], cwd: Optional[Path] = None, print_output: bool = False
) -> Tuple[subprocess.Popen[str], str, str]:
    try:

        process = subprocess.Popen(
            args,
            stdin=sys.stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            text=True,
            cwd=cwd,
            env={
                **os.environ,
                "DOCKER_BUILDKIT": "1",
                "LANG": "C.UTF-8",
                "LANGUAGE": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "BUILDKIT_PROGRESS": "plain",
            },
        )
        os.system(command='stty sane')

        stdout_capture: List[str] = []
        stderr_capture: List[str] = []
        if not process.stdout or not process.stderr:
            raise DatallogRuntimeError(
                stdout="",
                stderr="Failed to start process: stdout or stderr is None.",
            )
        
        stdout_tee = StreamTee(process.stdout, sys.stdout, stdout_capture, print_output)
        stderr_tee = StreamTee(process.stderr, sys.stderr, stderr_capture, print_output)

        stdout_tee.start()
        stderr_tee.start()

        return_code = process.wait()
        
        # Wait for the reader threads to finish processing any remaining buffered output
        stdout_tee.join()
        stderr_tee.join()
        
        final_stdout = "".join(stdout_capture)
        final_stderr = "".join(stderr_capture)
        if return_code != 0:
            raise subprocess.CalledProcessError(
                returncode=return_code,
                cmd=args,
                output=final_stdout,
                stderr=final_stderr,
            )

        return process, final_stdout, final_stderr
    except subprocess.CalledProcessError as e:
        stderr = e.stderr
        stdout = e.stdout
        if os.getenv("DATALLOG_LOG_LEVEL", "INFO").upper() == "DEBUG":
            print(stdout)
            print(stderr)

        if "Cannot connect to the Docker daemon" in stderr:
            raise CannotConnectToDockerDaemonError(
                "Cannot connect to the Docker daemon. Please ensure that Docker is running."
            )
        else:
            raise DatallogRuntimeError(
                stdout=stdout,
                stderr=stderr,
            ) from e


def conteiner_run(
    settings: Settings,
    runtime_image: str,
    command: str,
    volumes: List[Tuple[Path, Path]],
    args: List[str] = [],
    docker_args: List[str] = [],
    print_output: bool = False,
) -> Tuple[subprocess.Popen[str], str, str]:
    """
    Execute a command in the container.

    Args:
        command (str): The command to execute.
        *args (str): Additional arguments for the command.
    """
    volumes_args = [("-v", f"{volume[0]}:{volume[1]}:Z") for volume in volumes]
    volumes_args_list = [item for sublist in volumes_args for item in sublist]
    
    permissions_args = ["--user", f"{os.getuid()}:{os.getgid()}"]
    if settings.conteiner_engine == "podman":
        permissions_args = ["--userns=keep-id"]
    
    
    
    conteiner_command = [
        settings.conteiner_engine,
        "run",
        *volumes_args_list,
        "--rm",
        "-it",
        *permissions_args,
        "--platform",
        "linux/amd64",
        *docker_args,
        "datallog-runtime-" + runtime_image,
        command,
        *args,
    ]
    return conteiner_exec(conteiner_command, print_output=print_output)


def conteiner_build(settings: Settings, image_name: str) -> Tuple[subprocess.Popen[str], str, str]:
    dockerfile = Path.cwd() / ".." / "runtimes" / image_name
    args = [
        settings.conteiner_engine,
        "buildx",
        "build",
        "--no-cache",
        "--platform",
        "linux/amd64",
        "-t",
        "datallog-runtime-" + image_name,
        "-f",
        str(dockerfile),
        str(Path.cwd() / ".." / "runtimes"),
    ]

    return conteiner_exec(args, cwd=Path.cwd() / ".." / "runtimes")


def conteiner_install_packages(
    settings: Settings,
    requirements_file: Path,
    env_dir: Path,
    runtime_image: str,
) -> None:
    """
    Install packages in a container.

    Args:
        requirements_file (Path): Path to the requirements file.
        env_dir (Path): Directory for the virtual environment.
        runtime_image (str): image to use for the runtime.
    """

    conteiner_run(
        settings=settings,
        runtime_image=runtime_image,
        command="/install_packages.sh",
        volumes=[
            (requirements_file, Path("/requirements.txt")),
            (env_dir, Path("/env")),
        ],
    )


def conteiner_install_from_requirements(
    settings: Settings,
    requirements_file: Path,
    env_dir: Path,
    runtime_image: str,
    new_requirements: Path,
) -> Tuple[subprocess.Popen[str], str, str]:

    return conteiner_run(
        settings=settings,
        runtime_image=runtime_image,
        command="/install_packages.sh",
        args=["requirements"],
        volumes=[
            (requirements_file, Path("/requirements.txt")),
            (env_dir, Path("/env")),
            (new_requirements, Path("/new_requirements.txt")),
        ],
    )


def conteiner_install_from_packages_list(
    settings: Settings,
    requirements_file: Path,
    env_dir: Path,
    runtime_image: str,
    packages: List[str],
) -> Tuple[subprocess.Popen[str], str, str]:
    """
    Install packages in a container from a list.

    Args:
        requirements_file (Path): Path to the requirements file (to save).
        env_dir (Path): Directory for the virtual environment.
        runtime_image (str): image to use for the runtime.
        packages (List[str]): List of packages to install.
    """

    return conteiner_run(
        settings=settings,
        runtime_image=runtime_image,
        command="/install_packages.sh",
        args=["packages", *packages],
        volumes=[
            (requirements_file, Path("/requirements.txt")),
            (env_dir, Path("/env")),
        ],
    )


def conteiner_generate_hash(
    settings: Settings, runtime_image: str, env_dir: Path, deploy_dir: Path
) -> Tuple[str, str]:
    """
    Generate a hash of the environment directory.

    Args:
        deploy_dir (Path): Directory of the virtual environment.

    Returns:
        Tuple[str, str]: A tuple containing the requirements hash and the application hash.
    """

    (_, stdout, _) = conteiner_run(
        settings=settings,
        runtime_image=runtime_image,
        volumes=[
            (deploy_dir, Path("/deploy")),
            (env_dir, Path("/env")),
        ],
        command="/gen_hash.sh",
    )
    
    stdout = stdout
    if not stdout:
        raise DatallogRuntimeError(
            stdout="",
            stderr="Failed to generate hash.",
        )

    requirements_hash = None
    app_hash = None

    for line in stdout.splitlines():
        if line.startswith("DATALLOG_REQUIREMENTS_HASH="):
            requirements_hash = line.split("=", 1)[1].strip()
        elif line.startswith("DATALLOG_APP_HASH="):
            app_hash = line.split("=", 1)[1].strip()
        
        if requirements_hash and app_hash:
            break

    if not requirements_hash or not app_hash:
        raise DatallogRuntimeError(
            stdout=stdout,
            stderr="Failed to parse hash output. Expected 'DATALLOG_REQUIREMENTS_HASH' and 'DATALLOG_APP_HASH'.",
        )

    return (requirements_hash, app_hash)


def conteiner_check_if_image_exists(
    settings: Settings,
    runtime_image: str,
) -> Literal["No", "Yes", "Outdated"]:
    """
    Check if a Docker image exists.

    Args:
        image_name (str): Name of the image.

    Returns:
        bool: True if the image exists, False otherwise.
    """

    _, stdout, _ = conteiner_exec(
        [settings.conteiner_engine, "images", "-q", "datallog-runtime-" + runtime_image]
    )
    state = bool(stdout.strip())
    if not state:
        return "No"
    _, stdout, _ = conteiner_exec(
        [
            settings.conteiner_engine,
            "inspect",
            "-f",
            "{{ .Created }}",
            "datallog-runtime-" + runtime_image,
        ]
    )
    date = stdout.strip()
    if not date:
        return "No"

    try:
        created_date = datetime.strptime(date, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        try:
            created_date = datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            try:
                created_date = datetime.fromisoformat(date.replace("Z", "+00:00"))
            except ValueError:
                try:
                    date = re.sub(r"\.\d+[\s\S]*?$", "Z", date)  # Remove fractional seconds and trailing text
                    if 'T' not in date:
                        date = date.replace(" ", "T")
                    created_date = datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ")
                except ValueError:
                    raise DatallogRuntimeError(
                        stdout="",
                        stderr=f"Unable to parse image creation date: {date}",
                    )

    if created_date.tzinfo is None:
        created_date = pytz.utc.localize(created_date)

    runtimes_path = Path.cwd() / ".." / "runtimes"
    dockerfile_path = runtimes_path / runtime_image
    if not dockerfile_path.exists():
        return "No"
    dockerfile_mtime = datetime.fromtimestamp(
        dockerfile_path.stat().st_mtime, tz=timezone.utc
    )
    if created_date < dockerfile_mtime:
        logger.info(
            f"Warning: Image 'datallog-runtime-{runtime_image}' is outdated. "
            f"Image created on {created_date}, but Dockerfile was modified on {dockerfile_mtime}."
        )
        return "Outdated"
    return "Yes"


def conteiner_run_app(
    settings: Settings,
    runtime_image: str,
    env_dir: Path,
    deploy_dir: Path,
    unix_socket_path: str,
    worker_id: int,
    log_to_dir: Optional[Path],
) -> Tuple[subprocess.Popen[str], str, str]:
    """
    Run an application in a container.

    Args:
        runtime_image (str): Image to use for the runtime.
        env_dir (Path): Directory of the virtual environment.
        deploy_dir (Path): Directory of the deployment.
        unix_socket_path (str): Path to the Unix socket for communication.
    """
    volumes = [
        (env_dir, Path("/env")),
        (deploy_dir, Path("/deploy")),
        (Path(unix_socket_path), Path("/tmp/datallog_worker.sock")),
    ]
    
    if log_to_dir:
        volumes.append((log_to_dir, Path("/logs")))
        
    args = ["-m", "datallog.utils.worker", str(worker_id)]

    return conteiner_run(
        settings=settings,
        runtime_image=runtime_image,
        command="/env/bin/python",
        volumes=volumes,
        args=args,
        docker_args=["-w", "/deploy"],
        print_output=True,
    )


def conteiner_generete_build(
    settings: Settings,
    runtime_image: str, deploy_dir: Path, env_dir: Path
) -> Dict[str, Any]:
    try:
        with NamedTemporaryFile(mode="w", delete=True, suffix=".json") as temp_file:
            temp_file_path = Path(temp_file.name)
            conteiner_run(
                settings=settings,
                runtime_image=runtime_image,
                command="/env/bin/python",
                volumes=[
                    (deploy_dir, Path("/deploy")),
                    (env_dir, Path("/env")),
                    (temp_file_path, Path("/build.json")),
                ],
                docker_args=["-w", "/deploy"],
                args=["-m", "datallog.utils.generate_build_file"],
            )
            with open(temp_file_path, "r") as f:
                build_data = json.load(f)
        return build_data
    except DatallogRuntimeError as e:
        raise UnableToBuildImageError(e.stdout)
