import sys
import threading
import time
import itertools
import os
import tempfile

def get_hex_color(hex_code: str) -> str:
    """Convert Hex color (ex: #FF5733) to ANSI code."""
    hex_code = hex_code.lstrip('#')
    # Convert pairs hex to integers RGB
    r, g, b = tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))
    # Returns ANSI code True color
    return f"\033[38;2;{r};{g};{b}m"

def rgb(r: int, g: int, b: int) -> str:
    return f"\033[38;2;{r};{g};{b}m"

RESET = "\033[0m"
BOLD = "\033[1m"
RED = rgb(248, 81, 73)
GREEN = rgb(52, 211, 153)
BLUE = rgb(73, 143, 255)
YELLOW = rgb(242, 204, 96)


class Spinner:
    def __init__(self, text: str = "", color: str = BLUE, interval: float = 0.1):
        self.text = text
        self.color = color
        self.interval = interval
        self._frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._running = False
        self._thread = None
        
        # Variables to store original file descriptors
        self._original_stdout_fd: int | None = None
        self._original_stderr_fd: int | None = None
        self._temp_capture = None 

    def _animate(self):
        if self._original_stdout_fd is None:
            return
        try:
            with os.fdopen(os.dup(self._original_stdout_fd), 'w') as original_stdout:
                for frame in itertools.cycle(self._frames):
                    if not self._running:
                        break
                    original_stdout.write(f"\r{self.color}{BOLD}{frame} {self.text}{RESET}")
                    original_stdout.flush()
                    time.sleep(self.interval)

                # Clean spinner on exit
                original_stdout.write("\r" + " " * (len(self.text) + 4) + "\r")
                original_stdout.flush()
        except OSError:
            pass

    def start(self, text: str | None = None):
        if text:
            self.text = text
        if self._running:
            return
        
        self._running = True
        
        # Save original file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        self._original_stdout_fd = os.dup(sys.stdout.fileno())
        self._original_stderr_fd = os.dup(sys.stderr.fileno())

        # Creates tempfile to store system outputs while spinner is running
        self._temp_capture = tempfile.TemporaryFile(mode='w+')

        # Redirects stdout and stderr to this tempfile
        os.dup2(self._temp_capture.fileno(), sys.stdout.fileno())
        os.dup2(self._temp_capture.fileno(), sys.stderr.fileno())
        
        self._thread = threading.Thread(target=self._animate)
        self._thread.daemon = True
        self._thread.start()

    def _restore_streams_and_print_captured(self):
        # Restores the stdout (to print what was captured)
        if self._original_stdout_fd is not None:
            os.dup2(self._original_stdout_fd, sys.stdout.fileno())
            os.close(self._original_stdout_fd)
            self._original_stdout_fd = None
            
        # Restores stderr
        if self._original_stderr_fd is not None:
            os.dup2(self._original_stderr_fd, sys.stderr.fileno())
            os.close(self._original_stderr_fd)
            self._original_stderr_fd = None

        # Reads what was captured and print into original stdout
        if self._temp_capture is not None:
            # points back to the start of the tempfile
            self._temp_capture.seek(0)
            captured_output = self._temp_capture.read()
            
            if captured_output:
                # Prints everything that was "hidden"
                sys.stdout.write(captured_output)
            
            self._temp_capture.close()
            self._temp_capture = None

    def succeed(self, message: str = "Done"):
        self._stop_spinner() 
        self._restore_streams_and_print_captured()
        print(f"{GREEN}{BOLD}✔ {message}{RESET}")

    def fail(self, message: str = "Failed"):
        self._stop_spinner()
        self._restore_streams_and_print_captured()
        print(f"{RED}{BOLD}✖ {message}{RESET}")

    def _stop_spinner(self):
        if not self._running:
            return
        self._running = False
        if self._thread:
            self._thread.join()
