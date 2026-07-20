import difflib
from argparse import Namespace
from datetime import datetime
from pathlib import Path

import requests

from errors import DatallogError, LoginRequiredError, NetworkError
from logger import Logger
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


def _get_token_and_project_path():
    project_path = None
    try:
        from get_project_base_dir import get_project_base_dir

        project_path = get_project_base_dir()
    except Exception:
        project_path = None

    token = retrieve_token(project_path)
    if not token:
        raise LoginRequiredError("You must be logged in to use repair commands.")
    return token, project_path


def _fetch_applied_patch(token, project, app):
    url = f"{datallog_url}/platform-api/repair/patch/{project}/{app}"
    try:
        resp = requests.get(url, headers=token, timeout=30)
    except requests.RequestException as e:
        raise NetworkError(f"Failed to reach backend: {e}")

    if resp.status_code == 404:
        try:
            msg = resp.json().get("error", "No applied repair found.")
        except ValueError:
            msg = "No applied repair found."
        raise DatallogError(msg)
    if not resp.ok:
        raise NetworkError(f"Backend returned {resp.status_code}: {resp.text[:200]}")

    try:
        return resp.json().get("data", {}) or {}
    except ValueError:
        raise NetworkError("Backend returned an invalid response.")


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
            print("Usage: datallog repair <diff|pull> <project> <app>")
    except DatallogError as e:
        message = getattr(e, "message", str(e))
        logger.error(message)
        print(f"{RED}{message}{RESET}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"{RED}Unexpected error: {e}{RESET}")


def _repair_diff(args: Namespace) -> None:
    token, project_path = _get_token_and_project_path()
    data = _fetch_applied_patch(token, args.project, args.app)

    base_dir = project_path or Path.cwd()
    patch = data.get("patch") or []
    explanation = data.get("patch_explanation")
    applied_at = data.get("applied_at")

    print(f"{BOLD}Cloud repair applied for '{args.app}'{RESET}")
    if applied_at:
        print(f"Applied at: {_format_ts(applied_at)}")
    if explanation:
        print(f"\n{explanation}")
    if not patch:
        print(f"\n{YELLOW}(no file changes recorded){RESET}")
        return

    for entry in patch:
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
            continue

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


def _repair_pull(args: Namespace) -> None:
    token, project_path = _get_token_and_project_path()
    data = _fetch_applied_patch(token, args.project, args.app)

    patch = data.get("patch") or []
    if not patch:
        print(f"{YELLOW}No repair files to pull for '{args.app}'.{RESET}")
        return

    base_dir = project_path or Path.cwd()
    written = []
    for entry in patch:
        rel_path = entry.get("path")
        content = entry.get("new_content", "")
        if not rel_path:
            continue

        target = _safe_target(base_dir, rel_path)
        if target is None:
            print(f"{RED}Skipping unsafe path outside the project: {rel_path}{RESET}")
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        written.append(rel_path)

    if not written:
        print(f"{YELLOW}Nothing was pulled.{RESET}")
        return

    print(f"{GREEN}Pulled {len(written)} file(s) for '{args.app}':{RESET}")
    for rel_path in written:
        print(f"  {rel_path}")
    print(
        f"\n{YELLOW}Review the changes, then run `datallog push` to keep the cloud in sync "
        f"with your local code.{RESET}"
    )
