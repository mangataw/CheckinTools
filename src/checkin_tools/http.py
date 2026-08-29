"""Conservative HTTP transport for credential-bearing requests."""

from __future__ import annotations

import time
from urllib.parse import urljoin, urlsplit

import requests


class UnsafeRedirectError(requests.RequestException):
    pass


class SafeHttpClient:
    retry_statuses = frozenset({500, 502, 503, 504})

    def __init__(self, base_url: str, timeout: float = 20, retries: int = 2) -> None:
        self.base_url = base_url.rstrip("/")
        self.hostname = urlsplit(self.base_url).hostname
        self.timeout = timeout
        self.retries = retries

    @staticmethod
    def new_session() -> requests.Session:
        session = requests.Session()
        session.headers.update(
            {"User-Agent": "CheckinTools/0.1 (+https://github.com/mangataw/CheckinTools)"}
        )
        return session

    def url(self, path: str) -> str:
        target = urljoin(f"{self.base_url}/", path)
        parsed = urlsplit(target)
        if parsed.scheme != "https" or parsed.hostname != self.hostname:
            raise UnsafeRedirectError("request target is outside the configured HTTPS host")
        return target

    def request(self, session: requests.Session, method: str, path: str, **kwargs: object):
        target = self.url(path)
        kwargs.pop("allow_redirects", None)
        last_error: requests.RequestException | None = None
        for attempt in range(self.retries + 1):
            try:
                response = session.request(
                    method, target, timeout=self.timeout, allow_redirects=False, **kwargs
                )
                redirects = 0
                while response.is_redirect or response.is_permanent_redirect:
                    redirects += 1
                    if redirects > 5:
                        raise UnsafeRedirectError("too many redirects")
                    target = self.url(response.headers.get("Location", ""))
                    response = session.request(
                        method, target, timeout=self.timeout, allow_redirects=False, **kwargs
                    )
                if response.status_code in self.retry_statuses and attempt < self.retries:
                    time.sleep(min(0.25 * (2**attempt), 1))
                    continue
                response.raise_for_status()
                return response
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_error = exc
                if attempt == self.retries:
                    raise
                time.sleep(min(0.25 * (2**attempt), 1))
        raise last_error or requests.RequestException("request failed")

    def get(self, session: requests.Session, path: str, **kwargs: object):
        return self.request(session, "GET", path, **kwargs)

    def post(self, session: requests.Session, path: str, **kwargs: object):
        return self.request(session, "POST", path, **kwargs)

