"""Thin HTTP wrapper around the Prometheus query API."""

import logging
from datetime import datetime

import requests

logger = logging.getLogger(__name__)


class PrometheusClient:
    def __init__(self, base_url: str, timeout: int = 10) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.timeout = timeout

    def query_instant(self, promql: str, at: datetime | None = None) -> list[dict]:
        """GET /api/v1/query — instant vector."""
        params: dict = {"query": promql}
        if at:
            params["time"] = at.timestamp()
        resp = self.session.get(f"{self.base_url}/api/v1/query", params=params, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            logger.warning("Prometheus query returned non-success: %s", data)
            return []
        return data["data"]["result"]

    def query_range(
        self,
        promql: str,
        start: datetime,
        end: datetime,
        step: str = "15s",
    ) -> list[dict]:
        """GET /api/v1/query_range — range matrix."""
        params = {
            "query": promql,
            "start": start.timestamp(),
            "end": end.timestamp(),
            "step": step,
        }
        resp = self.session.get(f"{self.base_url}/api/v1/query_range", params=params, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            logger.warning("Prometheus range query returned non-success: %s", data)
            return []
        return data["data"]["result"]

    def scalar_value(self, promql: str, default: float = 0.0) -> float:
        """Return the first scalar value from an instant query, or *default*."""
        result = self.query_instant(promql)
        try:
            return float(result[0]["value"][1])
        except (IndexError, KeyError, ValueError, TypeError):
            return default
