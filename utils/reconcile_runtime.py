from hashlib import sha256
from pathlib import Path

from logger import Logger

logger = Logger(__name__)


def _runtime_marker(project_path: Path, runtime: str) -> str:
    """
    Fingerprint of everything that determines the local interpreter / base image.

    For a versioned runtime that's just the runtime string. For 'custom' the base
    image is defined by the user's Dockerfile, so its content is part of the marker
    (trocar o `FROM` muda a base sem mudar a string 'custom').
    """
    payload = runtime or ""
    if runtime == "custom":
        dockerfile = project_path / "datallog.Dockerfile"
        if dockerfile.exists():
            payload += "\n" + dockerfile.read_text(encoding="utf-8")
    return sha256(payload.encode("utf-8")).hexdigest()


def reconcile_local_runtime(project_path: Path, runtime: str, env_path: Path) -> None:
    """
    Make the cached local environment consistent with the declared runtime.

    `env_path` (project-envs/<hash>) is keyed only by the project path, so a change
    of base image is invisible to it. We keep a sibling marker file and, when it no
    longer matches, wipe the cached env so the next install rebuilds it from the new
    base. The marker lives *outside* env_path so the in-container install script
    (which only touches /env) can't clobber it.
    """
    marker_file = Path(str(env_path) + ".runtime")
    current = _runtime_marker(project_path, runtime)

    if not marker_file.exists():
        # First time we track this env: just record it, don't force a rebuild.
        marker_file.write_text(current, encoding="utf-8")
        return

    if marker_file.read_text(encoding="utf-8") == current:
        return

    logger.info(f"Runtime changed; rebuilding local environment at {env_path}")
    if env_path.exists():
        import shutil
        for child in env_path.iterdir():
            # `is_dir()` follows symlinks, so a symlinked child (e.g. a venv's
            # `lib64 -> lib`) would reach `rmtree`, which refuses symlinks. Unlink
            # symlinks and plain files; only recurse into real directories.
            if child.is_symlink() or not child.is_dir():
                child.unlink()
            else:
                shutil.rmtree(child)
    marker_file.write_text(current, encoding="utf-8")
