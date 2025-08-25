import json
from pathlib import Path
import subprocess
from queue import LifoQueue
from threading import Lock, Thread
from typing import Any, List, Optional, Set, TYPE_CHECKING
from schema import (
    ExecutionProps,
    WorkItem,
    WorkerError,
)
import os
from container import container_run_app

if TYPE_CHECKING:
    from worker_server import WorkerServer
    from settings import Settings

class Execution:
    def __init__(
        self,
        *,
        settings: 'Settings',
        runtime_image: str,
        deploy_dir: Path,
        env_dir: Path,
        app_name: str,
        seed: Optional[Any] = None,
        parallelism: int = 1,
        log_to_dir: Optional[Path] = None,
        socket_path: str,
    ):
        self._runtime_image = runtime_image
        self._deploy_dir = deploy_dir
        self._env_dir = env_dir

        self._parallelism = parallelism
        self._log_to_dir = log_to_dir
        self._threads: List[Thread] = []
        self._work_item_queue: LifoQueue[WorkItem] = LifoQueue()
        self._execution_props = ExecutionProps(
            file_path=str(Path("/deploy") / "apps" / app_name / f"{app_name}.py"),
            log_to_dir='/logs' if log_to_dir else None,
        )

        self._results_lock = Lock()
        self._results: List[Any] = []

        self._idle_workers_lock = Lock()
        self._idle_workers: Set[int] = set()

        self._worker_end_counter_lock = Lock()
        self._worker_end_counter = 0

        self._worker_id = 0
        self._worker_id_lock = Lock()

        self._errors_lock = Lock()
        self._errors: List[WorkerError] = []

        self._socket_path = socket_path

        first_work_item = WorkItem(
            step_index=0,
            argument=seed,
            sequence=[0],
        )

        self.add_work_item(first_work_item)
        self.__server: Optional['WorkerServer'] = None
        
        self.__settings = settings

    def set_server(self, server: 'WorkerServer') -> None:
        self.__server = server
    

    def __get_worker_next_id(self) -> int:
        with self._worker_id_lock:
            self._worker_id += 1
            return self._worker_id

    def _process_result(self):
        results: List[Any] = []
        with self._results_lock:
            for result in self._results:
                results.append(result.result)
        os.system('stty sane')
        if len(results) == 0:
            print("None")
        elif len(results) == 1:
            print(json.dumps(results[0], indent=4))
        else:
            print(json.dumps(results, indent=4))
        

    def _adjust_thread_count(self):
        with self._idle_workers_lock:
            idle_pids_count = len(self._idle_workers)
            if (
                idle_pids_count < self._work_item_queue.qsize()
                and len(self._threads) < self._parallelism
            ):
                thread = Thread(
                    target=self._worker_process, args=(self.__get_worker_next_id(),)
                )
                thread.start()
                self._threads.append(thread)

    def add_work_item(self, work_item: WorkItem):
        self._work_item_queue.put(work_item)
        self._adjust_thread_count()

    def _worker_process(self, worker_id: int) -> None:
        try:
            os.system(command='stty sane')
            container_run_app(
                settings=self.__settings,
                runtime_image=self._runtime_image,
                env_dir=self._env_dir,
                deploy_dir=self._deploy_dir,
                unix_socket_path=self._socket_path,
                worker_id=worker_id,
                log_to_dir=self._log_to_dir,
                
            )
            self.add_worker_end_counter()

        except subprocess.CalledProcessError as e:
            print(f"Worker process: {e.stdout}")
            print(f"Worker process failed with error: {e.stderr}")

    def get_work_item(self, worker_id: int) -> Optional[WorkItem]:
        try:
            work_item = self._work_item_queue.get(block=False)
        except Exception:
            work_item = None

        with self._idle_workers_lock:
            self._idle_workers.discard(worker_id)

        if work_item is not None:
            return work_item
        else:
            return None

    def add_worker_end_counter(self) -> bool:
        with self._worker_end_counter_lock:
            self._worker_end_counter += 1
            os.system('stty sane')
            if self._worker_end_counter == len(self._threads):
                self._process_result()
                if self.__server:
                    self.__server.shutdown()

        return False

    @property
    def execution_props(self) -> ExecutionProps:
        return self._execution_props

    def add_result_worker(self, result: Any) -> None:
        with self._results_lock:
            self._results.append(result)

    def add_error_worker(self, error: WorkerError) -> None:
        with self._errors_lock:
            self._errors.append(error)

    def mark_worker_as_idle(self, worker_id: int) -> None:
        with self._idle_workers_lock:
            self._idle_workers.add(worker_id)
