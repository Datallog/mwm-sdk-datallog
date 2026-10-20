"""Publish the project's portal pages (`pages/<slug>.html`) on push.

A portal is HTML the platform hosts inside the project. Until now the only way
to change one was pasting it in the panel, so the page lived only in the
database and drifted from the code that it calls. With this, the page is a file
in the project and `datallog push` sends it together with the automations.

Only the content travels. The link, who has access and the automations marked
by hand belong to the panel and survive a republish, so the title is also kept
when the page already exists: the panel may have renamed it.
"""
import html
import re
from pathlib import Path
from typing import Dict, List
from urllib.parse import quote

import requests

from variables import datallog_url


PAGES_DIR = "pages"
# Same rule the backend enforces for the address; checking here fails before
# any request, with the file name in the message.
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,58}[a-z0-9]$")
TITLE_TAG = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
MAX_TITLE = 120


class PagePublishError(Exception):
    pass


def find_pages(project_path: Path) -> List[Path]:
    folder = project_path / PAGES_DIR
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.glob("*.html") if p.is_file())


def _title_from_html(content: str, slug: str) -> str:
    match = TITLE_TAG.search(content)
    title = html.unescape(match.group(1)).strip() if match else ""
    return (title or slug)[:MAX_TITLE]


def _page_url(project_name: str, slug: str) -> str:
    return f"{datallog_url}/platform-api/pages/{quote(project_name, safe='')}/{slug}"


def _current_title(project_name: str, slug: str, token: Dict[str, str]):
    response = requests.get(_page_url(project_name, slug), headers=token, timeout=30)
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise PagePublishError(
            f"could not read page '{slug}': {response.status_code} {response.text[:200]}"
        )
    return response.json().get("title")


def publish_pages(project_path: Path, project_name: str, token: Dict[str, str]) -> List[Dict]:
    """Publish every `pages/*.html`. Returns one entry per page, in file order.

    Stops at the first failure: a half-published set is easier to reason about
    when the error says which page broke.
    """
    published = []
    for path in find_pages(project_path):
        slug = path.stem
        if not SLUG.match(slug):
            raise PagePublishError(
                f"{PAGES_DIR}/{path.name}: the file name is the page address and "
                "must have 3 to 60 lowercase letters, numbers and hyphens"
            )
        content = path.read_text(encoding="utf-8")
        title = _current_title(project_name, slug, token) or _title_from_html(content, slug)
        response = requests.put(
            _page_url(project_name, slug),
            json={"title": title, "html": content},
            headers=token,
            timeout=60,
        )
        if response.status_code not in (200, 201):
            try:
                message = response.json().get("message", response.text)
            except ValueError:
                message = response.text
            raise PagePublishError(f"could not publish page '{slug}': {message}")
        published.append({"slug": slug, "title": title, "created": response.status_code == 201})
    return published
