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
    Resolve the current project from the folder, require authentication and read
    the project name from project.ini (same source `datallog push` uses).

    Repair is a project-level operation: it must run INSIDE a project folder and
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
        raise LoginRequiredError("You must be logged in to use repair commands.")

    project_ini = parse_project_ini(project_path / "project.ini")
    project_name = project_ini.get("project", "name")

    return token, project_path, project_name


def _fetch_project_patches(token, project):
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


def _reconcile_project(token, project, app_names):
    url = f"{datallog_url}/platform-api/repair/reconcile"
    try:
        resp = requests.post(
            url,
            headers=token,
            json={"project_name": project, "app_names": app_names},
            timeout=30,
        )
    except requests.RequestException as e:
        raise NetworkError(f"Failed to reconcile with backend: {e}")

    if not resp.ok:
        raise NetworkError(f"Backend returned {resp.status_code}: {resp.text[:200]}")


def _safe_target(base_dir: Path, rel_path: str):
    """Resolve rel_path under base_dir, guarding against path escape (zip-slip)."""
    base_resolved = base_dir.resolve()
    target = (base_dir / rel_path).resolve()
    if base_resolved != target and base_resolved not in target.parents:
        return None
    return target


def repair(args: Namespace) -> None:
    try:
        subcommand = getattr(args, "repair_command", None)
        if subcommand == "diff":
            _repair_diff(args)
        elif subcommand == "pull":
            _repair_pull(args)
        else:
            print("Usage: datallog repair <diff|pull>")
    except DatallogError as e:
        message = getattr(e, "message", str(e))
        logger.error(message)
        print(f"{RED}{message}{RESET}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"{RED}Unexpected error: {e}{RESET}")


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
        print(f"{YELLOW}(local file already matches the cloud repair){RESET}")
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


def _repair_diff(args: Namespace) -> None:
    token, project_path, project_name = _get_auth_and_project()
    patches = _fetch_project_patches(token, project_name)

    app_filter = getattr(args, "app", None)
    if app_filter:
        patches = [p for p in patches if p.get("app_name") == app_filter]
        if not patches:
            print(
                f"{YELLOW}No applied repair found for '{app_filter}' in "
                f"'{project_name}'.{RESET}"
            )
            return

    if not patches:
        print(f"{YELLOW}No cloud repairs to review for '{project_name}'.{RESET}")
        return

    for app_patch in patches:
        app_name = app_patch.get("app_name", "?")
        patch = app_patch.get("patch") or []
        explanation = app_patch.get("patch_explanation")
        applied_at = app_patch.get("applied_at")

        print(f"\n{BOLD}Cloud repair applied for '{app_name}'{RESET}")
        if applied_at:
            print(f"Applied at: {_format_ts(applied_at)}")
        if explanation:
            print(f"\n{explanation}")
        if not patch:
            print(f"\n{YELLOW}(no file changes recorded){RESET}")
            continue

        for entry in patch:
            _print_file_diff(project_path, entry)


def _repair_pull(args: Namespace) -> None:
    token, project_path, project_name = _get_auth_and_project()
    patches = _fetch_project_patches(token, project_name)

    if not patches:
        print(f"{YELLOW}No applied repairs to pull for '{project_name}'.{RESET}")
        return

    reconciled_apps = []
    total_files = 0

    for app_patch in patches:
        app_name = app_patch.get("app_name")
        if not app_name:
            continue

        patch = app_patch.get("patch") or []
        app_written = []
        unsafe_skipped = 0

        for entry in patch:
            rel_path = entry.get("path")
            content = entry.get("new_content", "")
            if not rel_path:
                continue

            target = _safe_target(project_path, rel_path)
            if target is None:
                print(f"{RED}Skipping unsafe path outside the project: {rel_path}{RESET}")
                unsafe_skipped += 1
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            app_written.append(rel_path)

        # An app's cloud repair is "pulled" once it is represented locally: either
        # we wrote its files, or it had no file changes to write. If every path was
        # blocked as unsafe, we keep its drift flag (do not reconcile it).
        if app_written or (not patch and unsafe_skipped == 0):
            reconciled_apps.append(app_name)
            total_files += len(app_written)
            if app_written:
                print(f"{GREEN}{app_name}{RESET}: {len(app_written)} file(s)")
                for rel_path in app_written:
                    print(f"  {rel_path}")
            else:
                print(f"{GREEN}{app_name}{RESET}: no file changes to pull")

    if not reconciled_apps:
        print(f"{YELLOW}Nothing was pulled.{RESET}")
        return

    _reconcile_project(token, project_name, reconciled_apps)

    apps_str = ", ".join(reconciled_apps)
    print(
        f"\n{GREEN}Pulled {len(reconciled_apps)} app(s): {apps_str}. "
        f"Project reconciled — you can now run `datallog push` normally.{RESET}"
    )
