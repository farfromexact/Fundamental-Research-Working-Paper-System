from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
import time
from typing import Any, Callable
from urllib import parse, request


DEFAULT_BASE_URL = "https://proxy.keystock.com.cn/hydata/api"


class DzhApiError(RuntimeError):
    """Raised when DataApi returns an HTTP or business error."""


@dataclass(frozen=True)
class PagedResponse:
    rows: list[dict[str, Any]]
    reccount: int | None
    page_size: int
    pages_fetched: int
    duplicate_rows: int = 0


Transport = Callable[[str, dict[str, str], int], dict[str, Any]]


class DzhClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 30,
        sleep_seconds: float = 0.0,
        transport: Transport | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("DZH_API_KEY")
        if not self.api_key:
            raise ValueError("DZH_API_KEY is required")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.sleep_seconds = sleep_seconds
        self._transport = transport

    def _request_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}?{parse.urlencode(_drop_none(params))}"
        headers = {
            "Hydata-Apikey": self.api_key,
            "User-Agent": "earnings-signal/1.0",
        }
        if self._transport:
            payload = self._transport(url, headers, self.timeout)
        else:
            req = request.Request(url, headers=headers)
            try:
                with request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    payload = json.loads(raw)
            except Exception as exc:  # pragma: no cover - exercised by live calls
                raise DzhApiError(f"DataApi request failed for {path}: {exc}") from exc

        if isinstance(payload, dict) and "status" in payload and payload.get("status", 200) >= 400:
            code = payload.get("code")
            message = payload.get("message")
            raise DzhApiError(f"DataApi business error {code}: {message}")
        return payload

    def paged_get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        page_size: int = 200,
        max_pages: int | None = None,
        id_fields: tuple[str, ...] = ("ReportID", "CompId", "NewsId", "InfoId", "nID"),
    ) -> PagedResponse:
        if page_size <= 0 or page_size > 200:
            raise ValueError("page_size must be between 1 and 200")
        params = dict(params or {})
        rows: list[dict[str, Any]] = []
        seen: set[tuple[Any, ...] | str] = set()
        duplicates = 0
        reccount: int | None = None
        pages_fetched = 0

        while True:
            pno = pages_fetched + 1
            if max_pages is not None and pno > max_pages:
                break
            payload = self._request_json(path, params | {"psize": page_size, "pno": pno})
            page_rows = payload.get("rows") or []
            if reccount is None:
                reccount = payload.get("reccount")
            pages_fetched += 1

            for row in page_rows:
                key = _row_key(row, id_fields)
                if key in seen:
                    duplicates += 1
                    continue
                seen.add(key)
                rows.append(row)

            if reccount is not None:
                expected_pages = max(1, math.ceil(reccount / page_size))
                if pages_fetched >= expected_pages:
                    break
            elif len(page_rows) < page_size:
                break

            if self.sleep_seconds:
                time.sleep(self.sleep_seconds)

        return PagedResponse(rows, reccount, page_size, pages_fetched, duplicates)

    def research_reports(self, stock: str, start_date: str | None = None, end_date: str | None = None) -> PagedResponse:
        return self.paged_get(
            "/RReport",
            {"stock": stock, "startdate": start_date, "enddate": end_date, "brief": 1},
        )

    def ir_activities(self, stock: str, start_date: str | None = None, end_date: str | None = None) -> PagedResponse:
        return self.paged_get(
            "/Disclosure/iractivity",
            {"stock": stock, "startdate": start_date, "enddate": end_date},
        )

    def negative_news(self, stock: str, start_date: str | None = None, end_date: str | None = None) -> PagedResponse:
        return self.paged_get(
            "/News/neg",
            {"stock": stock, "startdate": start_date, "enddate": end_date, "brief": 1},
        )

    def disclosures(self, stock: str, start_date: str | None = None, end_date: str | None = None) -> PagedResponse:
        return self.paged_get(
            "/Disclosure/stock",
            {"stock": stock, "startdate": start_date, "enddate": end_date},
        )

    def compinfo(self, stock: str, start_date: str | None = None, end_date: str | None = None) -> PagedResponse:
        return self.paged_get(
            "/CompInfo/list",
            {"stocks": stock, "startdate": start_date, "enddate": end_date, "brief": 1},
        )

    def download_precheck(self, infotype: int, infoid: int) -> dict[str, Any]:
        return self._request_json("/Download", {"infotype": infotype, "infoid": infoid, "precheck": "true"})


def _drop_none(params: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in params.items() if v is not None}


def _row_key(row: dict[str, Any], id_fields: tuple[str, ...]) -> tuple[Any, ...] | str:
    for field in id_fields:
        if field in row and row[field] is not None:
            return (field, row[field])
    return json.dumps(row, sort_keys=True, ensure_ascii=False)

