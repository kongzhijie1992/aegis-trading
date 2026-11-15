"""Bounded HTTPS reads; credentials stay in memory and out of stored metadata."""

import json
import re
import time
from collections.abc import Mapping
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import DataError
from .providers import mapping, sequence


class PublicDataClient:
    def __init__(self) -> None:
        self.last_request = 0.0

    def read(self, url: str, headers: Mapping[str, str] | None = None) -> bytes:
        for attempt in range(3):
            time.sleep(max(0.0, 0.25 - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            try:
                request = Request(url, headers=dict(headers or {}))
                with urlopen(request, timeout=30) as response:
                    payload = response.read(64 * 1024 * 1024 + 1)
                if len(payload) > 64 * 1024 * 1024:
                    raise DataError("Provider response exceeds 64 MiB")
                return cast(bytes, payload)
            except HTTPError as exc:
                if exc.code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(2**attempt)
                    continue
                raise DataError(
                    f"Provider request failed (HTTP {exc.code}); check access/configuration"
                ) from None
            except (URLError, TimeoutError):
                raise DataError("Provider connection failed; no payload was stored") from None
        raise DataError("Provider retries exhausted")

    def sec(self, cik: str, user_agent: str) -> bytes:
        if not cik.isdigit() or len(cik) > 10:
            raise DataError("Use an explicit numeric SEC CIK, at most 10 digits")
        if "@" not in user_agent or any(c in user_agent for c in "\r\n"):
            raise DataError("Set SEC_USER_AGENT to an organization/app and public contact email")
        return self.read(
            f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json",
            {"User-Agent": user_agent, "Accept": "application/json"},
        )

    def fred(self, series: str, key: str | None = None) -> bytes:
        if not re.fullmatch(r"[A-Za-z0-9_]{1,80}", series):
            raise DataError("Invalid FRED series ID")
        if key is None:
            return self.read(
                "https://fred.stlouisfed.org/graph/fredgraph.csv?" + urlencode({"id": series})
            )
        if not re.fullmatch(r"[A-Za-z0-9]{16,128}", key):
            raise DataError("Invalid FRED_API_KEY format")
        params = {
            "series_id": series,
            "api_key": key,
            "file_type": "json",
            "output_type": 1,
            "realtime_start": "1776-07-04",
            "realtime_end": "9999-12-31",
            "limit": 100000,
        }
        payload = self.read(
            "https://api.stlouisfed.org/fred/series/observations?" + urlencode(params)
        )
        data = mapping(json.loads(payload))
        count = data.get("count")
        if type(count) is not int or count != len(sequence(data.get("observations"))):
            raise DataError("Incomplete FRED response; pagination is required before ingestion")
        return payload
