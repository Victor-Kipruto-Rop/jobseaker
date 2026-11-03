import re
from html.parser import HTMLParser
from html import unescape
import httpx
from packages.integrations.url_validation import validate_http_url

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")

class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, data):
        value = data.strip()
        if value:
            self.parts.append(value)

def plain_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value or "")
    return " ".join(parser.parts)[:30000]

def _safe_url(value: str) -> str:
    try:
        return validate_http_url(value, allow_empty=False)
    except ValueError:
        return ""

def _validate_slug(slug: str) -> str:
    slug = slug.strip().lower()
    if not _SLUG.fullmatch(slug):
        raise ValueError("Invalid job board identifier")
    return slug

async def discover_greenhouse(board: str, limit: int = 100) -> list[dict]:
    board = _validate_slug(board)
    async with httpx.AsyncClient(timeout=httpx.Timeout(15, connect=5),
                                 headers={"User-Agent": "JobSeeker-Intelligence/0.3"}) as client:
        response = await client.get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
                                    params={"content": "true"})
        response.raise_for_status()
        payload = response.json()
    jobs = []
    for item in payload.get("jobs", [])[:limit]:
        location = (item.get("location") or {}).get("name", "")
        jobs.append({
            "title": item.get("title") or "Untitled role",
            "company": board.replace("-", " ").title(),
            "description": plain_text(item.get("content", "")),
            "source_name": "greenhouse",
            "source_url": _safe_url(item.get("absolute_url", "")),
            "location": location,
            "employment_type": "unspecified",
            "remote_type": "unspecified",
        })
    return jobs

async def discover_lever(site: str, limit: int = 100) -> list[dict]:
    site = _validate_slug(site)
    async with httpx.AsyncClient(timeout=httpx.Timeout(15, connect=5),
                                 headers={"User-Agent": "JobSeeker-Intelligence/0.3"}) as client:
        response = await client.get(f"https://api.lever.co/v0/postings/{site}",
                                    params={"mode": "json"})
        response.raise_for_status()
        payload = response.json()
    jobs = []
    for item in payload[:limit]:
        categories = item.get("categories") or {}
        jobs.append({
            "title": item.get("text") or "Untitled role",
            "company": site.replace("-", " ").title(),
            "description": (item.get("descriptionPlain") or plain_text(item.get("description", "")))[:30000],
            "source_name": "lever",
            "source_url": _safe_url(item.get("hostedUrl") or item.get("applyUrl", "")),
            "location": categories.get("location", ""),
            "employment_type": categories.get("commitment", "unspecified"),
            "remote_type": "unspecified",
        })
    return jobs
