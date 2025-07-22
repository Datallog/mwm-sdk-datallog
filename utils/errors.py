class DatallogError(Exception):
    """Base class for all custom exceptions in the Datallog application."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

class InvalidAppError(DatallogError):
    """Custom exception for invalid app configurations."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
        
class EmptyDeployDirError(DatallogError):
    """Custom exception for empty deploy directory."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
        

        
class CannotConnectToDockerDaemonError(DatallogError):
    """Custom exception for issues connecting to the Docker daemon."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
        
        
class LoginRequiredError(DatallogError):
    """Custom exception for operations that require user login."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
        
class InvalidLoginToken(DatallogError):
    """Custom exception for invalid login tokens."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

class NotLoggedInError(DatallogError):
    """Custom exception for operations attempted without being logged in."""
    def __init__(self, message: str = "You are not logged in."):
        super().__init__(message)
        self.message = message
        
class NetworkError(DatallogError):
    """Custom exception for network-related errors."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
        
class DatallogRuntimeError(DatallogError):
    """Custom exception for errors related to the Datallog runtime."""
    def __init__(self, stdout: str, stderr: str):
        message = f"Datallog runtime error occurred.\nSTDOUT: {stdout}\nSTDERR: {stderr}"
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr
        self.message = message

class UnableToBuildImageError(DatallogError):
    """Custom exception for errors when building Docker images."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
        
class UnableToBundleAppError(DatallogError):
    """Custom exception for errors when bundling applications."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
        
class UnableToFindPythonExecutableError(DatallogError):
    """Custom exception for errors when finding the Python executable."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
        
class UnableToCreateVirtualEnvError(DatallogError):
    """Custom exception for errors when creating a virtual environment."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
        
class UnableToInstallPackagesError(DatallogError):
    """Custom exception for errors when installing packages."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
        
class UnableToSaveConfigError(DatallogError):
    """Custom exception for errors when saving configuration files."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
        
class UnableToCreateDeployError(DatallogError):
    """Custom exception for errors when creating a deployment."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
        
class InvalidSettingsError(DatallogError):
    """Custom exception for errors related to invalid settings."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message