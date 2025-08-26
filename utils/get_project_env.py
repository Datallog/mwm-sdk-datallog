from pathlib import Path
from hashlib import sha256


def get_project_env(project_path: Path) -> Path:
    """
    Generates a unique path for the project environment based on the provided project path.
    Args:
        project_path (Path): The path to the project directory.
    Returns:
        pathlib.Path: A resolved path to the project environment directory.
    Raises:
        ValueError: If the project path is not a valid directory.
    """
    project_path = project_path.resolve()
    hash_object = sha256()
    hash_object.update(str(project_path).encode("utf-8"))
    project_hash = hash_object.hexdigest()

    path = Path.cwd() / ".." / "project-envs" / project_hash
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    return path.resolve()
