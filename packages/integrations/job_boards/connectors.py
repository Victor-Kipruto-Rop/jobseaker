import re
from urllib.parse import urljoin, urlsplit
from html.parser import HTMLParser
import httpx
from packages.integrations.url_validation import validate_http_url

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")

class _BrandMetadataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}
        self.links = {}
        self.title_parts = []
        self.logo_images = []
        self.social_links = {}
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        values = {key.lower(): value for key, value in attrs if key and value}
        if tag.lower() == "meta":
            key = (values.get("property") or values.get("name") or "").lower()
            if key and values.get("content"):
                self.meta[key] = values["content"].strip()
        elif tag.lower() == "link":
            rel = values.get("rel", "").lower()
            href = values.get("href")
            if href and any(token in rel for token in ("icon", "canonical")):
                self.links[rel] = href
        elif tag.lower() == "a":
            href = values.get("href", "")
            host = (urlsplit(href).hostname or "").lower().removeprefix("www.")
            social_hosts = {
                "linkedin.com": "linkedin", "x.com": "x", "twitter.com": "x",
                "github.com": "github", "facebook.com": "facebook",
                "youtube.com": "youtube", "instagram.com": "instagram",
            }
            for domain, key in social_hosts.items():
                if host == domain or host.endswith("." + domain):
                    self.social_links[key] = href
                    break
        elif tag.lower() == "img":
            image_hint = " ".join((values.get("alt", ""), values.get("title", ""), values.get("class", ""))).casefold()
            if values.get("src") and any(word in image_hint for word in ("logo", "brand", "company")):
                self.logo_images.append(values["src"])
        elif tag.lower() == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title and data.strip():
            self.title_parts.append(data.strip())


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
        safe = validate_http_url(value, allow_empty=False)
        return safe if len(safe) <= 2000 else ""
    except ValueError:
        return ""


_SKILLS = (
    "Python", "SQL", "PostgreSQL", "MySQL", "Snowflake", "BigQuery", "Redshift",
    "Databricks", "Spark", "PySpark", "Kafka", "Airflow", "Dagster", "dbt",
    "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Terraform", "Flink",
    "Java", "Scala", "Go", "Pandas", "NumPy", "Power BI", "Tableau", "Looker",
    "Git", "Linux", "REST APIs", "FastAPI", "Flask",
)


def extract_required_skills(description: str) -> list[str]:
    """Extract only known technology mentions; this is evidence, not an inferred requirement."""
    text = (description or "").casefold()
    return [skill for skill in _SKILLS
            if re.search(r"(?<![a-z0-9])" + re.escape(skill.casefold()) + r"(?![a-z0-9])", text)]


def infer_remote_type(location: str, description: str = "", published_type: str = "") -> str:
    value = " ".join((location or "", description or "", published_type or "")).casefold()
    if "hybrid" in (published_type or "").casefold() or "hybrid" in value:
        return "hybrid"
    if any(term in value for term in ("remote", "distributed", "work from home", "work-from-home")):
        return "remote"
    if any(term in (published_type or "").casefold() for term in ("on-site", "onsite", "office")):
        return "onsite"
    return "unspecified"


def _epoch_datetime(value):
    try:
        from datetime import datetime, timezone
        if isinstance(value, str) and not value.strip().replace(".", "", 1).isdigit():
            from datetime import datetime, timezone
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
        numeric = float(value)
        if numeric > 10_000_000_000:
            numeric /= 1000
        return datetime.fromtimestamp(numeric, tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None

def _validate_slug(slug: str) -> str:
    slug = slug.strip().lower()
    if not _SLUG.fullmatch(slug):
        raise ValueError("Invalid job board identifier")
    return slug


async def discover_company_profile(source: str, board: str) -> dict:
    """Read public branding metadata from the ATS-hosted company board."""
    board = _validate_slug(board)
    if source == "greenhouse":
        page_url = f"https://job-boards.greenhouse.io/{board}"
    elif source == "lever":
        page_url = f"https://jobs.lever.co/{board}"
    else:
        raise ValueError("Unsupported job board provider")

    profile = {
        "company": board.replace("-", " ").title(),
        "company_website": "",
        "company_domain": "",
        "company_logo_url": "",
        "company_favicon_url": "",
        "company_description": "",
        "company_brand_color": "",
        "company_social_links": {},
        "company_brand_source": "",
    }
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(12, connect=4),
            follow_redirects=False,
            headers={"User-Agent": "JobSeeker-Intelligence/0.3"},
        ) as client:
            if source == "greenhouse":
                board_response = await client.get(f"https://boards-api.greenhouse.io/v1/boards/{board}")
                if board_response.status_code == 200:
                    board_payload = board_response.json()
                    if isinstance(board_payload, dict) and isinstance(board_payload.get("name"), str) and board_payload["name"].strip():
                        profile["company"] = board_payload["name"].strip()[:250]

            response = await client.get(page_url)
            if response.status_code != 200 or "text/html" not in response.headers.get("content-type", "").lower():
                return profile
            parser = _BrandMetadataParser()
            parser.feed(response.text[:1_000_000])

        meta = parser.meta
        title = meta.get("og:site_name") or meta.get("application-name") or ""
        if not title and parser.title_parts:
            candidate_title = parser.title_parts[0].strip()
            if candidate_title.casefold() not in {"careers", "jobs", "job openings", "open positions"}:
                title = candidate_title
        if title and profile["company"] == board.replace("-", " ").title():
            cleaned = re.split(r"\s+[|–—-]\s+", title.strip())[0].strip()
            if 1 < len(cleaned) <= 250:
                profile["company"] = cleaned

        description = meta.get("og:description") or meta.get("description") or ""
        profile["company_description"] = re.sub(r"\s+", " ", description).strip()[:2000]
        logo = meta.get("og:image") or meta.get("twitter:image") or (parser.logo_images[0] if parser.logo_images else "")
        theme_color = meta.get("theme-color", "").strip()
        if re.fullmatch(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?", theme_color):
            profile["company_brand_color"] = theme_color.lower()
        icon = parser.links.get("icon") or parser.links.get("shortcut icon") or ""
        logo_url = _safe_url(urljoin(page_url, logo)) if logo else ""
        icon_url = _safe_url(urljoin(page_url, icon)) if icon else ""
        profile["company_logo_url"] = logo_url if urlsplit(logo_url).scheme == "https" else ""
        profile["company_favicon_url"] = icon_url if urlsplit(icon_url).scheme == "https" else ""
        profile["company_social_links"] = {
            key: safe for key, value in parser.social_links.items()
            if (safe := _safe_url(urljoin(page_url, value))) and urlsplit(safe).scheme == "https"
        }

        canonical = parser.links.get("canonical") or meta.get("og:url") or ""
        if canonical:
            canonical_url = _safe_url(urljoin(page_url, canonical))
            host = urlsplit(canonical_url).hostname or ""
            ats_hosts = {"boards.greenhouse.io", "job-boards.greenhouse.io", "jobs.lever.co", "api.lever.co"}
            domain = host.lower().removeprefix("www.")
            if (canonical_url and len(canonical_url) <= 1000 and len(domain) <= 253
                    and urlsplit(canonical_url).scheme == "https" and host.lower() not in ats_hosts):
                profile["company_website"] = canonical_url
                profile["company_domain"] = domain
        board_name = board.replace("-", " ").title()
        if profile["company"] != board_name or any(profile[key] for key in (
            "company_logo_url", "company_favicon_url", "company_website",
            "company_description", "company_brand_color", "company_social_links",
        )):
            profile["company_brand_source"] = page_url
    except (httpx.HTTPError, ValueError, UnicodeError):
        return profile
    return profile


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
            "remote_type": infer_remote_type(location, plain_text(item.get("content", ""))),
            "required_skills": extract_required_skills(plain_text(item.get("content", ""))),
            "posted_at": _epoch_datetime(item.get("updated_at")),
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
            "location": categories.get("allLocations") or categories.get("location", ""),
            "employment_type": categories.get("commitment", "unspecified"),
            "remote_type": infer_remote_type(
                categories.get("location", ""), item.get("descriptionPlain") or item.get("description", ""),
                categories.get("workplaceType", ""),
            ),
            "required_skills": extract_required_skills(
                item.get("descriptionPlain") or plain_text(item.get("description", ""))
            ),
            "posted_at": _epoch_datetime(item.get("createdAt")),
        })
    return jobs


def filter_jobs(jobs: list[dict], *, keywords: list[str] | None = None,
                location: str | None = None, remote_only: bool = False) -> list[dict]:
    """Apply deterministic saved-search filters to normalized job records."""
    normalized_keywords = [item.strip().casefold() for item in (keywords or []) if item.strip()]
    location_term = (location or "").strip().casefold()
    remote_terms = ("remote", "distributed", "work from home", "work-from-home", "anywhere")
    filtered = []
    for job in jobs:
        title = str(job.get("title") or "")
        description = str(job.get("description") or "")
        job_location = str(job.get("location") or "")
        haystack = f"{title} {description}".casefold()
        if normalized_keywords and not any(term in haystack for term in normalized_keywords):
            continue
        if location_term and location_term not in f"{job_location} {description}".casefold():
            continue
        if remote_only and not any(term in f"{title} {description} {job_location}".casefold()
                                   for term in remote_terms):
            continue
        filtered.append(job)
    return filtered
