"""Thin HTTP wrapper around the Grafana Tempo search API."""

import logging
from datetime import datetime

import requests

logger = logging.getLogger(__name__)


class TempoClient:
    def __init__(self, base_url: str, timeout: int = 15) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.timeout = timeout

    def search(
        self,
        service_name: str,
        start: datetime,
        end: datetime,
        limit: int = 20,
    ) -> list[dict]:
        """GET /api/search — return trace summaries for a service."""
        params = {
            "tags": f"service.name={service_name}",
            "start": int(start.timestamp()),
            "end": int(end.timestamp()),
            "limit": limit,
        }
        try:
            resp = self.session.get(
                f"{self.base_url}/api/search", params=params, timeout=self.timeout
            )
            resp.raise_for_status()
            return resp.json().get("traces", [])
        except requests.RequestException as exc:
            logger.warning("Tempo search failed: %s", exc)
            return []

    def search_traceql(
        self,
        query: str,
        start: datetime,
        end: datetime,
        limit: int = 10,
    ) -> list[dict]:
        """GET /api/search with a TraceQL *q* parameter."""
        params = {
            "q": query,
            "start": int(start.timestamp()),
            "end": int(end.timestamp()),
            "limit": limit,
        }
        try:
            resp = self.session.get(
                f"{self.base_url}/api/search", params=params, timeout=self.timeout
            )
            resp.raise_for_status()
            return resp.json().get("traces", [])
        except requests.RequestException as exc:
            logger.warning("Tempo TraceQL search failed: %s", exc)
            return []

    def get_trace(self, trace_id: str) -> dict | None:
        """GET /api/traces/{trace_id} — full trace with all spans."""
        try:
            resp = self.session.get(f"{self.base_url}/api/traces/{trace_id}", timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("Tempo get_trace(%s) failed: %s", trace_id, exc)
            return None
