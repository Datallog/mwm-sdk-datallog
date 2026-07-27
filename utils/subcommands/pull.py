from argparse import Namespace
from pathlib import Path

import requests

from errors import DatallogError, InvalidProjectError, LoginRequiredError, NetworkError
from get_project_base_dir import get_project_base_dir
from logger import Logger
from parser_project_ini import parse_project_ini
from token_manager import retrieve_token
from variables import datallog_url

logger = Logger(__name__)

YELLOW = "\033[93m"
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"


def _get_auth_and_project():
    """
    Resolve the current project from the folder, require authentication and read
    the project name from project.ini (same source `datallog push` uses).

    Pull is a project-level operation: it must run INSIDE a project folder and
    must never silently fall back to the current working directory.
    """
    try:
        project_path = get_project_base_dir()
    except InvalidProjectError:
        raise DatallogError(
            "No Datallog project found here. Run this inside your project folder."
        )

    token = retrieve_token(project_path)
    if not token:
        raise LoginRequiredError("You must be logged in to pull a project.")

    project_ini = parse_project_ini(project_path / "project.ini")
    project_name = project_ini.get("project", "name")

    return token, project_path, project_name


def _fetch_project_files(token, project_name):
    url = f"{datallog_url}/platform-api/agent/project-export"
    try:
        resp = requests.get(url, headers=token, params={"deploy_name": project_name}, timeout=30)
    except requests.RequestException as e:
        raise NetworkError(f"Failed to reach backend: {e}")

    if resp.status_code == 404:
        try:
            msg = resp.json().get("error", "Project not found.")
        except ValueError:
            msg = "Project not found."
        raise DatallogError(msg)
    if not resp.ok:
        raise NetworkError(f"Backend returned {resp.status_code}: {resp.text[:200]}")

    try:
        return resp.json().get("files", {}) or {}
    except ValueError:
        raise NetworkError("Backend returned an invalid response.")


def _reconcile_project(token, project_name, app_names):
    """Limpa a flag has_unsynced_repair dos apps puxados — sem isso, um
    `datallog push` normal continua sendo bloqueado com 409 mesmo depois
    de puxar a versão mais nova. Mesmo endpoint que `datallog repair pull`
    já usava antes desta mudança."""
    if not app_names:
        return
    url = f"{datallog_url}/platform-api/repair/reconcile"
    try:
        resp = requests.post(
            url, headers=token, json={"project_name": project_name, "app_names": app_names}, timeout=30,
        )
    except requests.RequestException as e:
        raise NetworkError(f"Failed to reconcile with backend: {e}")

    if not resp.ok:
        raise NetworkError(f"Backend returned {resp.status_code}: {resp.text[:200]}")


def _automation_names_in(files) -> list:
    """Deriva os nomes de automação presentes nos arquivos puxados, a
    partir do path `automations/{nome}/...` — usado só pra reconciliar o
    drift, nunca pra decidir o que escrever em disco."""
    names = set()
    for rel_path in files:
        parts = rel_path.split("/")
        if len(parts) >= 2 and parts[0] == "automations":
            names.add(parts[1])
    return sorted(names)


def _safe_target(base_dir: Path, rel_path: str):
    """Resolve rel_path under base_dir, guarding against path escape (zip-slip)."""
    base_resolved = base_dir.resolve()
    target = (base_dir / rel_path).resolve()
    if base_resolved != target and base_resolved not in target.parents:
        return None
    return target


def _execute_pull(token, project_path: Path, project_name: str, force: bool) -> None:
    """Core pull logic: full overwrite of the local project with whatever is
    live on the server. Shared by `datallog pull` and the deprecated
    `datallog repair pull`, which delegates here instead of keeping its own
    divergent implementation."""
    files = _fetch_project_files(token, project_name)

    if not files:
        print(f"{YELLOW}Nothing to pull for '{project_name}'.{RESET}")
        return

    if not force:
        existing = [rel_path for rel_path in sorted(files) if (project_path / rel_path).exists()]
        if existing:
            print(f"\n{YELLOW}The following local files will be OVERWRITTEN with the cloud version:{RESET}")
            for rel_path in existing:
                print(f"  {rel_path}")
            confirm = input("\nContinue? (y/N): ").strip().lower()
            if confirm != "y":
                print("Pull cancelled.")
                return

    written = 0
    for rel_path in sorted(files):
        target = _safe_target(project_path, rel_path)
        if target is None:
            print(f"{RED}Skipping unsafe path outside the project: {rel_path}{RESET}")
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(files[rel_path])
        written += 1

    print(f"\n{GREEN}{written} arquivos atualizados{RESET}")

    # Sem isso, um `datallog push` normal continua bloqueado com 409 mesmo
    # depois de puxar a versão mais nova (a flag de drift do Auto Reparo
    # só é limpa explicitamente, nunca por só ter o arquivo em disco).
    _reconcile_project(token, project_name, _automation_names_in(files))


def _pull_command(args: Namespace) -> None:
    token, project_path, project_name = _get_auth_and_project()
    force = getattr(args, "force", False)
    _execute_pull(token, project_path, project_name, force)


def pull(args: Namespace) -> None:
    try:
        _pull_command(args)
    except DatallogError as e:
        message = getattr(e, "message", str(e))
        logger.error(message)
        print(f"{RED}{message}{RESET}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"{RED}Unexpected error: {e}{RESET}")
