import difflib
from argparse import Namespace
from datetime import datetime
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
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _format_ts(ts):
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M")
    except (ValueError, OSError, TypeError):
        return str(ts)


def _get_auth_and_project():
    """
    Resolve the current project from the folder and require authentication —
    same source `datallog push`/`datallog pull` use.

    Diff is a project-level operation: it must run INSIDE a project folder and
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
        raise LoginRequiredError("You must be logged in to use diff.")

    project_ini = parse_project_ini(project_path / "project.ini")
    project_name = project_ini.get("project", "name")

    return token, project_path, project_name


def _fetch_project_changes(token, project):
    """Puxa a correção mais recente aplicada em produção pra cada automação
    com drift — Auto Reparo OU o agente de IA (publicar via chat), o que
    for mais recente (o backend já resolve isso, ver
    resolve_latest_applied_change)."""
    url = f"{datallog_url}/platform-api/repair/patches/{project}"
    try:
        resp = requests.get(url, headers=token, timeout=30)
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
        return resp.json().get("data", []) or []
    except ValueError:
        raise NetworkError("Backend returned an invalid response.")


def _print_file_diff(base_dir: Path, entry: dict) -> None:
    rel_path = entry.get("path", "?")
    new_content = entry.get("new_content", "")
    print(f"\n{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}{rel_path}{RESET}")
    print(f"{BLUE}{'=' * 70}{RESET}")

    old_content = ""
    local_file = base_dir / rel_path
    if local_file.exists():
        old_content = local_file.read_text(encoding="utf-8", errors="replace")

    if old_content == new_content:
        print(f"{YELLOW}(local file already matches the cloud version){RESET}")
        return

    diff_lines = difflib.unified_diff(
        old_content.splitlines(),
        new_content.splitlines(),
        fromfile=f"local/{rel_path}",
        tofile=f"cloud/{rel_path}",
        lineterm="",
    )
    for line in diff_lines:
        if line.startswith("+") and not line.startswith("+++"):
            print(f"{GREEN}{line}{RESET}")
        elif line.startswith("-") and not line.startswith("---"):
            print(f"{RED}{line}{RESET}")
        else:
            print(line)


def _diff_command(args: Namespace) -> None:
    token, project_path, project_name = _get_auth_and_project()
    changes = _fetch_project_changes(token, project_name)

    app_filter = getattr(args, "app", None)
    if app_filter:
        changes = [c for c in changes if c.get("app_name") == app_filter]
        if not changes:
            print(
                f"{YELLOW}No applied change found for '{app_filter}' in "
                f"'{project_name}'.{RESET}"
            )
            return

    if not changes:
        print(f"{YELLOW}No cloud changes to review for '{project_name}'.{RESET}")
        return

    for app_change in changes:
        app_name = app_change.get("app_name", "?")
        patch = app_change.get("patch") or []
        explanation = app_change.get("patch_explanation")
        applied_at = app_change.get("applied_at")

        print(f"\n{BOLD}Cloud change applied for '{app_name}'{RESET}")
        if applied_at:
            print(f"Applied at: {_format_ts(applied_at)}")
        if explanation:
            print(f"\n{explanation}")
        if not patch:
            print(f"\n{YELLOW}(no file changes recorded){RESET}")
            continue

        for entry in patch:
            _print_file_diff(project_path, entry)


def diff(args: Namespace) -> None:
    try:
        _diff_command(args)
    except DatallogError as e:
        message = getattr(e, "message", str(e))
        logger.error(message)
        print(f"{RED}{message}{RESET}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"{RED}Unexpected error: {e}{RESET}")
