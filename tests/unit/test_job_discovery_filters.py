from packages.integrations.job_boards.connectors import filter_jobs

JOBS = [
    {"title": "Senior Data Engineer", "description": "Build Spark and Kafka pipelines",
     "location": "Nairobi, Kenya"},
    {"title": "Analytics Engineer", "description": "dbt, SQL and BI models",
     "location": "Remote - Africa"},
    {"title": "Platform Engineer", "description": "Kubernetes and infrastructure",
     "location": "London, UK"},
]

def test_keyword_filter_matches_any_configured_keyword_case_insensitively():
    result = filter_jobs(JOBS, keywords=["SPARK", "dbt"])
    assert [job["title"] for job in result] == ["Senior Data Engineer", "Analytics Engineer"]

def test_location_filter_uses_location_and_description():
    assert [job["title"] for job in filter_jobs(JOBS, location="nairobi")] == ["Senior Data Engineer"]

def test_remote_filter_is_explicit_and_excludes_onsite_roles():
    assert [job["title"] for job in filter_jobs(JOBS, remote_only=True)] == ["Analytics Engineer"]

def test_empty_filters_preserve_all_normalized_jobs():
    assert filter_jobs(JOBS) == JOBS


def test_company_board_metadata_uses_published_name_and_https_brand_assets(monkeypatch):
    import asyncio
    import packages.integrations.job_boards.connectors as connectors

    class Response:
        def __init__(self, status_code, payload=None, text="", content_type="application/json"):
            self.status_code = status_code
            self._payload = payload or {}
            self.text = text
            self.headers = {"content-type": content_type}

        def json(self):
            return self._payload

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url):
            if "boards-api.greenhouse.io" in url:
                return Response(200, {"name": "Acme Financial"})
            return Response(
                200,
                text=(
                    '<html><head><meta property="og:site_name" content="Acme Financial">'
                    '<meta property="og:description" content="Payments infrastructure">'
                    '<meta name="theme-color" content="#123456">'
                    '<meta property="og:image" content="/brand/logo.svg">'
                    '<link rel="icon" href="/favicon.ico">'
                    '<link rel="canonical" href="https://acme.example/careers">'
                    '<a href="https://www.linkedin.com/company/acme">LinkedIn</a>'
                    '<a href="https://github.com/acme">GitHub</a>'
                    '</head><body></body></html>'
                ),
                content_type="text/html; charset=utf-8",
            )

    monkeypatch.setattr(connectors.httpx, "AsyncClient", lambda **kwargs: Client())
    result = asyncio.run(connectors.discover_company_profile("greenhouse", "acme"))

    assert result["company"] == "Acme Financial"
    assert result["company_website"] == "https://acme.example/careers"
    assert result["company_domain"] == "acme.example"
    assert result["company_logo_url"] == "https://job-boards.greenhouse.io/brand/logo.svg"
    assert result["company_favicon_url"] == "https://job-boards.greenhouse.io/favicon.ico"
    assert result["company_description"] == "Payments infrastructure"
    assert result["company_brand_color"] == "#123456"
    assert result["company_social_links"] == {
        "linkedin": "https://www.linkedin.com/company/acme",
        "github": "https://github.com/acme",
    }
    assert result["company_brand_source"] == "https://job-boards.greenhouse.io/acme"


def test_company_profile_does_not_invent_missing_brand_assets(monkeypatch):
    import asyncio
    import packages.integrations.job_boards.connectors as connectors

    class Response:
        status_code = 200
        headers = {"content-type": "text/html"}
        text = "<html><head><title>Careers</title></head></html>"

        def json(self):
            return {}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url):
            return Response()

    monkeypatch.setattr(connectors.httpx, "AsyncClient", lambda **kwargs: Client())
    result = asyncio.run(connectors.discover_company_profile("lever", "acme"))

    assert result["company"] == "Acme"
    assert result["company_logo_url"] == ""
    assert result["company_favicon_url"] == ""
    assert result["company_website"] == ""
    assert result["company_brand_source"] == ""


def test_job_parser_extracts_known_skills_without_matching_partial_words():
    from packages.integrations.job_boards.connectors import extract_required_skills

    skills = extract_required_skills(
        "Build Python and Kafka data pipelines with PostgreSQL, dbt and Docker. "
        "The role is not about unrelated abbreviations."
    )
    assert skills == ["Python", "PostgreSQL", "Kafka", "dbt", "Docker"]


def test_remote_type_uses_published_workplace_signal_and_does_not_guess():
    from packages.integrations.job_boards.connectors import infer_remote_type

    assert infer_remote_type("Nairobi, Kenya", "Work from anywhere") == "remote"
    assert infer_remote_type("Nairobi", "", "Hybrid") == "hybrid"
    assert infer_remote_type("London, UK", "", "On-site") == "onsite"
    assert infer_remote_type("Nairobi, Kenya", "Join our engineering team") == "unspecified"


def test_job_posting_timestamp_parser_accepts_epoch_and_iso_values():
    from packages.integrations.job_boards.connectors import _epoch_datetime

    epoch = _epoch_datetime(1_700_000_000_000)
    iso = _epoch_datetime("2024-01-02T03:04:05Z")
    assert epoch is not None and epoch.year == 2023
    assert iso is not None and iso.isoformat() == "2024-01-02T03:04:05+00:00"
