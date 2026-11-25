"""Complete production collection surface reviewed against Oura OpenAPI 1.42."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Collection:
    name: str
    kind: str = "date"
    path_name: str = ""

    @property
    def path(self):
        return "/v2/usercollection/" + (self.path_name or self.name)

    def parameters(self, start: date, end: date, timezone="UTC"):
        """Half-open [start, end); filter the response to the same window too."""
        if self.kind == "static":
            return {}
        if self.kind == "datetime":
            tz = ZoneInfo(timezone)
            return {
                "start_datetime": datetime.combine(start, time.min, tz).isoformat(),
                "end_datetime": datetime.combine(end, time.min, tz).isoformat(),
            }
        # Sleep filters use bedtime dates, while returned `day` is the Oura
        # reporting day. A lookbehind prevents losing overnight periods at a
        # partition boundary; enforce the canonical source day locally.
        return {
            "start_date": (start - timedelta(days=7)).isoformat(),
            "end_date": (end + timedelta(days=1)).isoformat(),
        }


COLLECTIONS = {
    c.name: c
    for c in [
        Collection("daily_activity"),
        Collection("daily_cardiovascular_age"),
        Collection("daily_readiness"),
        Collection("daily_resilience"),
        Collection("daily_sleep"),
        Collection("daily_spo2"),
        Collection("daily_stress"),
        Collection("enhanced_tag"),
        Collection("heartrate", "datetime"),
        Collection("personal_info", "static"),
        Collection("rest_mode_period"),
        Collection("ring_battery_level", "datetime"),
        Collection("ring_configuration", "static"),
        Collection("session"),
        Collection("sleep"),
        Collection("sleep_time"),
        Collection("tag"),
        Collection("vo2_max", path_name="vO2_max"),
        Collection("workout"),
    ]
}


def record_day(item, timezone="UTC"):
    for name in ("day", "start_day"):
        if item.get(name):
            return str(item[name])[:10]
    for name in (
        "timestamp",
        "start_datetime",
        "start_time",
        "bedtime_start",
        "set_up_at",
    ):
        if item.get(name):
            parsed = datetime.fromisoformat(str(item[name]).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("Source timestamp has no timezone")
            return parsed.astimezone(ZoneInfo(timezone)).date().isoformat()
    return None


def record_key(endpoint, item):
    if item.get("id"):
        return str(item["id"])
    if item.get("timestamp"):
        return str(item["timestamp"]) + ":" + str(item.get("source", ""))
    if item.get("day"):
        return str(item["day"])
    raise ValueError(f"{endpoint}: source record has no stable identity")


def month_windows(start, end):
    cursor = start
    while cursor < end:
        following = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
        stop = min(following, end)
        yield cursor, stop
        cursor = stop
