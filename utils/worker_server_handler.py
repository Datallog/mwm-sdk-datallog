from socketserver import StreamRequestHandler
from typing import Optional, TYPE_CHECKING

from schema import (
    GetWorkItem,
    GetExecutionProps,
    ExecutionProps,
    NoMoreWorkItems,
    WorkItem,
    WorkerMarkAsIdle,
    WorkerPublishResult,
    WorkerError,
    WorkerMessage,
)

if TYPE_CHECKING:
    from worker_server import WorkerServer


class ExecutionWorkerHandler(StreamRequestHandler):
    def _send_message_to_worker(
        self, message: WorkItem | ExecutionProps | NoMoreWorkItems
    ) -> None:
        """
        Sends a message to the worker process.
        """
        self.wfile.write(message.model_dump_json().encode() + b"\n")
        self.wfile.flush()

    def _receive_message_from_worker(
        self,
    ) -> Optional[
        GetWorkItem
        | GetExecutionProps
        | WorkItem
        | WorkerPublishResult
        | WorkerMarkAsIdle
        | WorkerError
    ]:
        """
        Receives a message from the worker process.
        """
        self.server: "WorkerServer" # type: ignore
        msg = self.rfile.readline()
        if not msg:
            return None
        model = WorkerMessage.validate_json(msg)
        return model

    def handle(self):
        while True:
            worker_message = self._receive_message_from_worker()
            if not worker_message:
                break

            if worker_message.type == "GET_WORK_ITEM":
                work_item = self.server.execution.get_work_item(
                    worker_id=worker_message.worker_id
                )

                if work_item is not None:
                    self._send_message_to_worker(work_item)
                else:
                    self._send_message_to_worker(NoMoreWorkItems())
                    break

            elif worker_message.type == "GET_STEP_EXECUTION_PROPS":
                self._send_message_to_worker(self.server.execution.execution_props)
            elif worker_message.type == "WORK_ITEM":
                self.server.execution.add_work_item(work_item=worker_message)
            elif worker_message.type == "PUBLISH_RESULT":
                self.server.execution.add_result_worker(worker_message)
            elif worker_message.type == "WORKER_ERROR":
                self.server.execution.add_error_worker(worker_message)
            elif worker_message.type == "MARK_AS_IDLE":
                self.server.execution.mark_worker_as_idle(worker_message.worker_id)
