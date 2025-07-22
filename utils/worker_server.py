from pathlib import Path
import random
import string
import tempfile
from socketserver import ThreadingMixIn, UnixStreamServer
from typing import Any, Optional, TYPE_CHECKING
from execution import Execution
from worker_server_handler import ExecutionWorkerHandler
from pathlib import Path

if TYPE_CHECKING:
    from settings import Settings

class WorkerServer(ThreadingMixIn, UnixStreamServer):
    def __init__(
        self,
        settings: 'Settings',
        runtime_image: str,
        deploy_dir: Path,
        env_dir: Path,
        app_name: str,
        seed: Optional[Any] = None,
        parallelism: int = 1,
        log_to_dir: Optional[Path] = None,
    ):
        socket_path = self.__generate_socket_path()
        self._execution = Execution(
            settings=settings,
            runtime_image=runtime_image,
            deploy_dir=deploy_dir,
            env_dir=env_dir,
            app_name=app_name,
            seed=seed,
            parallelism=parallelism,
            log_to_dir=log_to_dir,
            socket_path=socket_path,
        )
        self._execution.set_server(self)
        super().__init__(socket_path, ExecutionWorkerHandler)
        socket_path = Path(socket_path)

    def __generate_socket_path(self) -> str:
        temp_dir = Path(tempfile.gettempdir())
        random_part = "".join(
            random.choices(string.ascii_letters + string.digits, k=10)
        )

        socket_path = temp_dir / f"datallog_worker_{random_part}.sock"
        socket_path = socket_path.resolve()
        
        if socket_path.exists():
            socket_path.unlink()  # Remove the old socket file if it exists
        return str(socket_path)

    @property
    def execution(self) -> Execution:
        return self._execution
