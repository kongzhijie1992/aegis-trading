"""Source dates, first-seen times and exact values are separate concepts."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation


class DataError(ValueError):
    pass


def timestamp(value: datetime) -> str:
    if value.utcoffset() is None:
        raise DataError("Timezone-aware ingestion/as-of timestamps required")
    return value.astimezone(UTC).isoformat(timespec="microseconds")


def number(value: object) -> str | None:
    if value is None or value in (".", ""):
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise DataError("Observation value must be numeric or missing")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise DataError("Invalid numeric observation") from exc
    if not parsed.is_finite() or abs(parsed.adjusted()) > 100:
        raise DataError("Nonfinite or excessive observation value")
    result = format(parsed, "f")
    return "0" if parsed == 0 else result.rstrip("0").rstrip(".") if "." in result else result


@dataclass(frozen=True)
class Observation:
    source: str
    entity: str
    metric: str
    unit: str
    period_end: str
    available_at: datetime
    revision: str
    value: str | None
    period_start: str = ""
    basis: str = "first_seen"

    def validate(self) -> None:
        if not all((self.source, self.entity, self.metric, self.unit, self.revision, self.basis)):
            raise DataError("Source/entity/metric/unit/revision/basis are required")
        end = date.fromisoformat(self.period_end)
        if end.isoformat() != self.period_end or (
            self.period_start
            and date.fromisoformat(self.period_start).isoformat() != self.period_start
        ):
            raise DataError("Periods require canonical YYYY-MM-DD dates")
        if self.period_start and date.fromisoformat(self.period_start) > end:
            raise DataError("Period start exceeds period end")
        timestamp(self.available_at)
        number(self.value)
