"""Normalize provider responses without flattening units or vintage identities."""

import csv
import io
import json
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import cast
from zoneinfo import ZoneInfo

from .models import DataError, Observation, number


def mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise DataError("Expected a JSON object")
    return cast(dict[str, object], value)


def sequence(value: object) -> list[object]:
    if not isinstance(value, list):
        raise DataError("Expected a JSON array")
    return cast(list[object], value)


def text(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise DataError("Required nonempty string missing")
    return value


def next_day(day: str, zone: str) -> datetime:
    # Date-only evidence is available AFTER that whole local day, not at midnight
    # at its start. This is a conservative proxy, not an exact publication time.
    return datetime.combine(
        date.fromisoformat(day) + timedelta(days=1), time.min, ZoneInfo(zone)
    ).astimezone(UTC)


def sec_facts(payload: bytes) -> list[Observation]:
    data = mapping(json.loads(payload, parse_float=Decimal))
    cik = str(data.get("cik", ""))
    if not cik.isdigit() or len(cik) > 10:
        raise DataError("SEC payload requires a numeric CIK")
    entity = "CIK" + cik.zfill(10)
    rows = []
    for taxonomy, concepts in mapping(data.get("facts")).items():
        for tag, concept in mapping(concepts).items():
            for unit, items in mapping(mapping(concept).get("units")).items():
                for item in sequence(items):
                    fact = mapping(item)
                    if "val" not in fact:
                        raise DataError("SEC fact is missing val")
                    rows.append(
                        Observation(
                            "sec",
                            entity,
                            taxonomy + "." + tag,
                            unit,
                            text(fact.get("end")),
                            next_day(text(fact.get("filed")), "America/New_York"),
                            text(fact.get("accn")),
                            number(fact.get("val")),
                            str(fact.get("start", "")),
                            "filing_date_end_proxy",
                        )
                    )
    return rows


def fred_vintages(payload: bytes, series: str, unit: str) -> list[Observation]:
    data = mapping(json.loads(payload, parse_float=Decimal))
    if (
        data.get("realtime_start") != "1776-07-04"
        or data.get("realtime_end") != "9999-12-31"
        or data.get("output_type") != 1
    ):
        raise DataError("Vintage ingestion requires the full realtime window and output_type=1")
    rows = []
    for item in sequence(data.get("observations")):
        observation = mapping(item)
        vintage = text(observation.get("realtime_start"))
        rows.append(
            Observation(
                "fred-vintage",
                "US",
                series,
                unit,
                text(observation.get("date")),
                next_day(vintage, "America/Chicago"),
                vintage,
                number(observation.get("value")),
                basis="vintage_date_end_proxy",
            )
        )
    return rows


def fred_current_csv(
    payload: bytes, series: str, unit: str, ingested_at: datetime
) -> list[Observation]:
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
    if not reader.fieldnames or series not in reader.fieldnames:
        raise DataError("CSV series column does not match the requested FRED ID")
    date_key = "observation_date" if "observation_date" in reader.fieldnames else "DATE"
    return [
        Observation(
            "fred-current",
            "US",
            series,
            unit,
            text(item.get(date_key)),
            ingested_at,
            "current",
            number(item.get(series)),
            basis="current_download_first_seen",
        )
        for item in reader
    ]


def records_csv(payload: bytes, source: str) -> list[Observation]:
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
    required = {"entity", "metric", "unit", "period_end", "available_at", "revision", "value"}
    if not required.issubset(reader.fieldnames or []):
        raise DataError("CSV requires entity,metric,unit,period_end,available_at,revision,value")
    return [
        Observation(
            source,
            text(item.get("entity")),
            text(item.get("metric")),
            text(item.get("unit")),
            text(item.get("period_end")),
            datetime.fromisoformat(text(item.get("available_at"))),
            text(item.get("revision")),
            number(item.get("value")),
            item.get("period_start", "") or "",
            item.get("basis", "imported_availability") or "imported_availability",
        )
        for item in reader
    ]
