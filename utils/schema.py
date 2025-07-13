from typing import Annotated, Any, List, Optional, cast
from uuid import UUID

from pydantic import BaseModel, Field, TypeAdapter
from typing import Any, Literal, Optional
from uuid import UUID, uuid4


class GetWorkItem(BaseModel):
    """
    Represents a request sent by a worker process to the conteiner server
    to ask for a new work item (a specific step to execute).
    """

    type: Literal["GET_WORK_ITEM"] = "GET_WORK_ITEM"
    """Identifies the type of message being sent."""
    worker_id: int
    """The worker ID of the worker sending the request. Used by the server
    to identify which worker is asking for a task."""


class GetExecutionProps(BaseModel):
    """
    Represents a request sent by a worker process to the conteiner server,
    typically during initialization, to retrieve static properties
    associated with the overall application execution it will be part of.
    """

    type: Literal["GET_STEP_EXECUTION_PROPS"] = "GET_STEP_EXECUTION_PROPS"
    """Identifies the type of message being sent."""
    worker_id: int
    """The worker ID of the worker sending the request."""


class ExecutionProps(BaseModel):
    """
    Contains the static properties defining a specific application execution.
    This data is typically sent by the server to a worker process in response
    to a GetExecutionProps request or upon initial assignment, providing the
    context needed to run the application's steps.
    """

    type: Literal["EXECUTION_PROPS"] = "EXECUTION_PROPS"
    """Identifies the type of message being sent."""

    file_path: str
    """The absolute or relative path to the main Python file containing the
       user's application code (steps defined with decorators). The worker
       needs this to import the code."""

    execution_id: UUID = Field(default_factory=uuid4)
    """The unique identifier for this entire application execution instance.
       All work items and results related to this specific run will share
       this ID."""

    log_to_dir: Optional[str] = None
    """Optional directory path where the worker can log its output. If provided,
       the worker should write its logs to this directory. If None, no logging
       directory is specified, and the worker logs may go to standard output
    """


class WorkItem(BaseModel):
    """
    Represents a single unit of work - a specific step execution task - sent
    by the conteiner server to a worker process. It contains all the necessary
    information for the worker to find and execute the correct step function.
    Can also be sent *by* the worker to the server to indicate the *next* step
    to be executed if the current step is not the final one.
    """

    type: Literal["WORK_ITEM"] = "WORK_ITEM"
    """Identifies the type of message, indicating this is a task for the worker
       or a request to schedule the next task."""
    work_id: UUID = Field(default_factory=uuid4)
    """A unique identifier for *this specific* instance of executing a step.
       If a step branches, each new resulting task gets its own unique work_id."""
    step_index: int
    """The zero-based index corresponding to the step function (defined via
       decorators in the user's code) that should be executed for this work item."""
    argument: Any
    """The input data or argument that should be passed to the step function
       when it is called by the worker."""
    from_work_id: Optional[UUID] = None
    """The work_id of the preceding WorkItem that generated this one. This creates
       a lineage or execution tree, linking steps together. It's None
       for the first step of an execution."""
    sequence: List[int] = Field(default_factory=list) # type: ignore
    """A list of integers representing the sequence of step indices leading to
         this WorkItem. This helps in tracking the execution path taken to reach
         this step, useful for debugging and understanding the flow of execution.""" 
         


class WorkerPublishResult(BaseModel):
    """
    Represents the final result message sent by a worker process back to the
    conteiner server after successfully completing a WorkItem.

    This message is sent *only* when the completed step is the *final step*
    in its specific execution path (i.e., no subsequent step is defined by
    the application's decorators). It signals the end of this execution
    branch and provides its final output value.

    If a subsequent step *is* defined for the completed WorkItem, the worker
    will instead send a message (like a 'step' type message, potentially formatted
    similarly to a WorkItem) to initiate that next step, rather than sending
    this final result message.
    """

    type: Literal["PUBLISH_RESULT"] = "PUBLISH_RESULT"
    """Identifies the type of message, indicating a final result report for an
       execution path."""
    work_id: UUID
    """The unique identifier of the specific WorkItem that completed and produced
       this final result."""
    result: Any
    """The actual final data returned by the last step function in this execution path."""


class WorkerError(BaseModel):
    """
    Represents a message sent by a worker process back to the conteiner server
    when an error occurs during the processing or execution of a WorkItem.
    """

    type: Literal["WORKER_ERROR"] = "WORKER_ERROR"
    """Identifies the type of message, indicating an error report."""
    error: str
    """A string summary of the error that occurred (e.g., exception message)."""
    traceback: str
    """A detailed string containing the full Python traceback associated with
       the error, for debugging purposes."""
    work_id: UUID | None = None
    """The unique identifier of the specific WorkItem during which the error
       occurred, helping to pinpoint the failure location."""


class NoMoreWorkItems(BaseModel):
    """
    Represents a message sent by the conteiner server to a worker process
    indicating that there are no more work items available for
    processing. This typically occurs when all tasks have been assigned
    and completed, signaling the worker to exit or wait for new tasks.
    """

    type: Literal["NO_MORE_WORK_ITEMS"] = "NO_MORE_WORK_ITEMS"
    """Identifies the type of message, indicating no more work items are available."""


class WorkerMarkAsIdle(BaseModel):
    """
    Represents a message sent by the conteiner server to a worker process
    to mark it as idle. This is typically used to indicate that the worker
    is not currently processing any tasks and is available for new work.
    """

    type: Literal["MARK_AS_IDLE"] = "MARK_AS_IDLE"
    """Identifies the type of message, indicating the worker should be marked as idle."""

    worker_id: int


WorkerMessage: TypeAdapter[
    Annotated[
        GetWorkItem
        | GetExecutionProps
        | WorkItem
        | WorkerPublishResult
        | WorkerMarkAsIdle
        | WorkerError,
        Field(discriminator="type"),
    ]
] = TypeAdapter(
    Annotated[
        GetWorkItem
        | GetExecutionProps
        | WorkItem
        | WorkerPublishResult
        | WorkerMarkAsIdle
        | WorkerError,
        Field(discriminator="type"),
    ]
)
