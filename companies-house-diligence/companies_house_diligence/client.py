"""Companies House API client.

Thin wrapper over the Public Data API (and Document API) with:
- HTTP Basic auth (API key as username, empty password)
- 429 rate-limit handling with Retry-After backoff
- simple on-disk JSON response caching (optional) keyed by path

API key is read from the COMPANIES_HOUSE_KEY environment variable, or from a
.env file in the project root.
"""

from __future__ import annotations

import os
import time
import json
import hashlib
import logging
from pathlib import Path
from typing import Any, Optional

import requests

LOG = logging.getLogger("ch.client")

PUBLIC_BASE = "https://api.company-information.service.gov.uk"
DOCUMENT_BASE = "https://document-api.company-information.service.gov.uk"


def _load_key() -> str:
    key = os.environ.get("COMPANIES_HOUSE_KEY")
    if key:
        return key.strip()
    # fall back to a .env file walking up from cwd
    here = Path.cwd()
    for d in [here, *here.parents]:
        env = d / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.startswith("COMPANIES_HOUSE_KEY="):
                    return line.split("=", 1)[1].strip()
    raise RuntimeError(
        "No Companies House API key found. Set COMPANIES_HOUSE_KEY or add it to .env"
    )


class CompaniesHouseClient:
    def __init__(
        self,
        key: Optional[str] = None,
        cache_dir: Optional[str | Path] = None,
        max_retries: int = 5,
        timeout: int = 30,
    ):
        self.key = key or _load_key()
        self.session = requests.Session()
        self.session.auth = (self.key, "")
        self.max_retries = max_retries
        self.timeout = timeout
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.call_count = 0

    # -- low level ---------------------------------------------------------
    def _cache_path(self, path: str, params: Optional[dict]) -> Optional[Path]:
        if not self.cache_dir:
            return None
        raw = path + "?" + json.dumps(params or {}, sort_keys=True)
        h = hashlib.sha1(raw.encode()).hexdigest()[:16]
        safe = path.strip("/").replace("/", "_")[:60]
        return self.cache_dir / f"{safe}_{h}.json"

    def get(
        self,
        path: str,
        params: Optional[dict] = None,
        base: str = PUBLIC_BASE,
        use_cache: bool = True,
    ) -> Optional[dict]:
        """GET a JSON resource. Returns parsed dict, or None on 404."""
        cache_path = self._cache_path(path, params) if use_cache else None
        if cache_path and cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))

        url = base + path
        for attempt in range(self.max_retries):
            self.call_count += 1
            resp = self.session.get(url, params=params, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                if cache_path:
                    cache_path.write_text(json.dumps(data), encoding="utf-8")
                return data
            if resp.status_code == 404:
                return None
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 5))
                LOG.warning("rate limited; sleeping %ss", wait)
                time.sleep(wait + 1)
                continue
            if 500 <= resp.status_code < 600:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
        raise RuntimeError(f"Failed after {self.max_retries} retries: {url}")

    def document_content(self, metadata_url: str, accept: str,
                         binary: bool = False):
        """Fetch a document's content from the Document API.

        `metadata_url` is the `.../document/<id>` link from filing history;
        `accept` is e.g. 'application/xhtml+xml' (iXBRL) or 'application/pdf'.
        Returns text (str) or, with binary=True, bytes. None on failure.
        """
        url = metadata_url.rstrip("/") + "/content"
        for attempt in range(self.max_retries):
            self.call_count += 1
            resp = self.session.get(url, headers={"Accept": accept},
                                    timeout=self.timeout)
            if resp.status_code == 200:
                return resp.content if binary else resp.text
            if resp.status_code in (404, 406, 410):
                return None
            if resp.status_code == 429:
                time.sleep(int(resp.headers.get("Retry-After", 5)) + 1)
                continue
            if 500 <= resp.status_code < 600:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
        return None

    # -- typed helpers -----------------------------------------------------
    def company(self, number: str) -> Optional[dict]:
        return self.get(f"/company/{number}")

    def officers(self, number: str, items_per_page: int = 100) -> dict:
        out = self.get(
            f"/company/{number}/officers",
            params={"items_per_page": items_per_page},
        )
        return out or {"items": []}

    def psc(self, number: str, items_per_page: int = 100) -> dict:
        out = self.get(
            f"/company/{number}/persons-with-significant-control",
            params={"items_per_page": items_per_page},
        )
        return out or {"items": []}

    def charges(self, number: str) -> dict:
        out = self.get(f"/company/{number}/charges")
        return out or {"items": [], "total_count": 0}

    def filing_history(self, number: str, category: Optional[str] = None,
                       items_per_page: int = 50) -> dict:
        params: dict[str, Any] = {"items_per_page": items_per_page}
        if category:
            params["category"] = category
        out = self.get(f"/company/{number}/filing-history", params=params)
        return out or {"items": []}

    def search_companies(self, q: str, items_per_page: int = 20) -> dict:
        out = self.get(
            "/search/companies",
            params={"q": q, "items_per_page": items_per_page},
        )
        return out or {"items": []}

    def advanced_search(self, **params) -> dict:
        out = self.get("/advanced-search/companies", params=params)
        return out or {"items": []}
