"""Data minimization boundary: subhourly telemetry never reaches storage."""

import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

SCHEMA_VERSION = 3
DISCARDED_FIELDS = {
    "class_5_min",
    "movement_30_sec",
    "sleep_phase_30_sec",
    "sleep_phase_5_min",
    "app_sleep_phase_5_min",
    "motion_count",
}
SAMPLE_FIELDS = {"met", "heart_rate", "hrv", "heart_rate_variability"}


def instant(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Telemetry timestamp has no timezone")
    return result.astimezone(timezone.utc)


def numeric(value):
    return (
        isinstance(value, (float, int))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def hour_start(stamp):
    return stamp.replace(minute=0, second=0, microsecond=0)


def aggregate_sample(sample):
    """PublicSample values represent intervals; split at UTC hour boundaries.

    Mean uses only observed duration. No interpolation across missing values.
    HRV is the mean of source HRV values, not recomputed hourly RMSSD.
    """
    if sample is None:
        return None
    interval = sample.get("interval")
    if not numeric(interval) or interval <= 0:
        raise ValueError("Invalid sample interval")
    stamp = instant(sample["timestamp"])
    buckets = defaultdict(
        lambda: {"sum": 0.0, "observed_seconds": 0.0, "missing_seconds": 0.0}
    )
    for index, value in enumerate(sample["items"]):
        if value is not None and not numeric(value):
            raise ValueError("Invalid telemetry value")
        cursor = stamp + timedelta(seconds=index * interval)
        stop = cursor + timedelta(seconds=interval)
        while cursor < stop:
            hour = hour_start(cursor)
            upper = min(stop, hour + timedelta(hours=1))
            seconds = (upper - cursor).total_seconds()
            bucket = buckets[hour]
            if value is None:
                bucket["missing_seconds"] += seconds
            else:
                bucket["sum"] += value * seconds
                bucket["observed_seconds"] += seconds
            cursor = upper
    hours = []
    for hour, bucket in sorted(buckets.items()):
        observed = bucket["observed_seconds"]
        hours.append(
            {
                "timestamp": hour.isoformat(),
                "mean": round(bucket["sum"] / observed, 6) if observed else None,
                "observed_seconds": observed,
                "missing_seconds": bucket["missing_seconds"],
            }
        )
    return {"aggregation": "hourly_interval_mean", "hours": hours}


def heart_rate(items, timezone_name):
    buckets = {}
    seen = {}
    for item in items:
        stamp = instant(item["timestamp"])
        source = item.get("source", "unknown")
        ident = (stamp, source)
        value = item.get("bpm")
        if value is not None and (not numeric(value) or value <= 0):
            raise ValueError("Invalid heart rate value")
        if ident in seen:
            if seen[ident] != value:
                raise ValueError("Conflicting heart rate samples")
            continue
        seen[ident] = value
        key = (hour_start(stamp), source)
        bucket = buckets.setdefault(key, {"values": [], "missing": 0, "minutes": set()})
        if value is None:
            bucket["missing"] += 1
        else:
            bucket["values"].append(value)
            bucket["minutes"].add(stamp.minute)
    result = []
    for (stamp, source), bucket in sorted(buckets.items()):
        values = bucket["values"]
        result.append(
            {
                "timestamp": stamp.isoformat(),
                "day": stamp.astimezone(ZoneInfo(timezone_name)).date().isoformat(),
                "source": source,
                "aggregation": "hourly_sample_mean",
                "mean_bpm": round(sum(values) / len(values), 6) if values else None,
                "samples": len(values),
                "missing_samples": bucket["missing"],
                "observed_minutes": len(bucket["minutes"]),
            }
        )
    return result


def battery_daily(items, timezone_name):
    buckets = defaultdict(list)
    for item in items:
        stamp = instant(item["timestamp"])
        if not numeric(item.get("level")) or not 0 <= item["level"] <= 100:
            raise ValueError("Invalid battery level")
        buckets[stamp.astimezone(ZoneInfo(timezone_name)).date().isoformat()].append(
            (stamp, item["level"])
        )
    return [
        {
            "day": day,
            "level": max(values)[1],
            "minimum_level": min(v for _, v in values),
            "sample_count": len(values),
            "aggregation": "daily",
        }
        for day, values in sorted(buckets.items())
    ]


def clean(value):
    if isinstance(value, dict):
        if "interval" in value and "items" in value:
            raise ValueError("Unclassified sampled field")
        return {
            key: aggregate_sample(item) if key in SAMPLE_FIELDS else clean(item)
            for key, item in value.items()
            if key not in DISCARDED_FIELDS
        }
    if isinstance(value, list):
        if value and all(item is None or numeric(item) for item in value):
            raise ValueError("Unclassified numeric series")
        return [clean(item) for item in value]
    return value


def minimize(endpoint, items, timezone_name="UTC"):
    if endpoint == "heartrate":
        return heart_rate(items, timezone_name)
    if endpoint == "ring_battery_level":
        return battery_daily(items, timezone_name)
    return [clean(item) for item in items]


def assert_minimized(endpoint, items):
    """Guard both the writer and independent downloaded-source verification."""

    def check(value):
        if isinstance(value, dict):
            if (
                DISCARDED_FIELDS.intersection(value)
                or "items" in value
                and "interval" in value
            ):
                raise ValueError("Subhourly series reached storage boundary")
            for item in value.values():
                check(item)
        elif isinstance(value, list):
            if value and all(item is None or numeric(item) for item in value):
                raise ValueError("Numeric series reached storage boundary")
            for item in value:
                check(item)

    check(items)
    for item in items:
        if endpoint == "heartrate":
            if item.get("aggregation") != "hourly_sample_mean" or "bpm" in item:
                raise ValueError("Raw heart rate reached storage boundary")
            stamp = instant(item["timestamp"])
            if stamp != hour_start(stamp):
                raise ValueError("Invalid hourly boundary")
        if endpoint == "ring_battery_level" and item.get("aggregation") != "daily":
            raise ValueError("Raw battery data reached storage boundary")
