from pathlib import Path
from hashlib import sha256


def get_deploy_env(deploy_path: Path) -> Path:
    """
    Generates a unique path for the deployment environment based on the provided deploy path.
    Args:
        deploy_path (Path): The path to the deployment directory.
    Returns:
        pathlib.Path: A resolved path to the deployment environment directory.
    Raises:
        ValueError: If the deploy path is not a valid directory.
    """
    deploy_path = deploy_path.resolve()
    hash_object = sha256()
    hash_object.update(str(deploy_path).encode("utf-8"))
    deploy_hash = hash_object.hexdigest()

    path = Path.cwd() / ".." / "deploy-envs" / deploy_hash
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    return path.resolve()
