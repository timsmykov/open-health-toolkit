"""Read Oura API v2 with an OAuth bearer or normalize a saved export."""
import json
import time
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .nutrition import known as nonnegative_number
from .oura_collections import COLLECTIONS, record_day, record_key
from .oura_hourly import assert_minimized, minimize


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def read_page(path, params, token):
    url = "https://api.ouraring.com" + path + ("?" + urlencode(params) if params else "")
    request = Request(url, headers={"Authorization": "Bearer " + token,
                                    "User-Agent": "open-health-toolkit/0.1"})
    opener = build_opener(NoRedirect)
    for attempt in range(4):
        try:
            with opener.open(request, timeout=30) as stream:
                return json.load(stream)
        except HTTPError as error:
            status = error.code
            if status not in (429, 500, 502, 503, 504) or attempt == 3:
                raise RuntimeError(f"Oura API returned HTTP {status}") from None
            wait = error.headers.get("Retry-After", "")
            time.sleep(min(int(wait), 60) if wait.isdecimal() else 2 ** attempt)
        except URLError:
            if attempt == 3:
                raise RuntimeError("Oura API connection failed") from None
            time.sleep(2 ** attempt)


def normalize(name, records, timezone):
    if name not in COLLECTIONS:
        raise ValueError("Unknown Oura collection")
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        raise ValueError("Oura records must be an array of objects")
    result = minimize(name, records, timezone)
    assert_minimized(name, result)
    return result


def fetch(name, start, end, timezone, token, *, page=read_page):
    if name not in COLLECTIONS or start >= end:
        raise ValueError("Choose an Oura collection and an increasing date window")
    if not token:
        raise ValueError("Set OURA_ACCESS_TOKEN to an Oura OAuth access token")
    collection = COLLECTIONS[name]
    records, outside = {}, 0
    cursor = start
    while cursor < end:
        stop = min(end, cursor + timedelta(days=7)) if collection.kind == "datetime" else end
        params = collection.parameters(cursor, stop, timezone)
        seen = set()
        while True:
            payload = page(collection.path, params, token)
            if not isinstance(payload, dict):
                raise ValueError("Unexpected Oura collection response")
            items = [payload] if name == "personal_info" else payload.get("data")
            if not isinstance(items, list) or any(not isinstance(row, dict) for row in items):
                raise ValueError("Unexpected Oura collection response")
            for row in items:
                if collection.kind != "static":
                    day = record_day(row, timezone)
                    if not day:
                        raise ValueError("Oura record is missing its date")
                    if not cursor.isoformat() <= day < stop.isoformat():
                        outside += 1
                        continue
                key = record_key(name, row)
                if key in records and records[key] != row:
                    raise ValueError("Conflicting records returned for one Oura ID")
                records[key] = row
            next_token = payload.get("next_token")
            if not next_token:
                break
            if not isinstance(next_token, str) or next_token in seen:
                raise ValueError("Oura pagination did not advance")
            seen.add(next_token)
            params = {**params, "next_token": next_token}
        cursor = stop
    return {"collection": name, "start": start.isoformat(), "end_exclusive": end.isoformat(),
            "timezone": timezone, "source_records": len(records), "out_of_window_records": outside,
            "records": normalize(name, [records[key] for key in sorted(records)], timezone)}


def report(bundles, end, days):
    """Summarize source days with per-metric coverage, using source sleep records."""
    if days not in (7, 28):
        raise ValueError("Choose a 7 or 28 day period")
    start = end - timedelta(days=days - 1)
    timezones = {bundle["timezone"] for bundle in bundles}
    if len(timezones) != 1:
        raise ValueError("Use a single timezone for all Oura bundles")
    timezone, = timezones
    daily, identities = {}, {}
    for bundle in bundles:
        name = bundle["collection"]
        if name not in ("daily_activity", "sleep"):
            raise ValueError("Oura summaries consume daily_activity and sleep bundles")
        for row in bundle["records"]:
            day = record_day(row, timezone)
            if day is None or not start.isoformat() <= day <= end.isoformat():
                continue
            identity = (name, record_key(name, row))
            if identity in identities and identities[identity] != row:
                raise ValueError("Conflicting versions of one source record")
            identities[identity] = row
            metrics = daily.setdefault(day, {})
            if name == "daily_activity":
                previous = metrics.setdefault("activity", row)
                if row != previous:
                    raise ValueError("Multiple daily activity records for one source day")
            elif row.get("type") == "long_sleep" and nonnegative_number(row.get("total_sleep_duration")):
                previous = metrics.get("sleep")
                # A stable ID breaks ties without depending on input order.
                order = lambda item: (item["total_sleep_duration"], record_key("sleep", item))
                if previous is None or order(row) > order(previous):
                    metrics["sleep"] = row
    result = {}
    for output, group, field in (
        ("steps", "activity", "steps"),
        ("main_sleep_seconds", "sleep", "total_sleep_duration"),
        ("main_sleep_mean_bpm", "sleep", "average_heart_rate"),
        ("main_sleep_low_bpm", "sleep", "lowest_heart_rate"),
        ("main_sleep_hrv_ms", "sleep", "average_hrv"),
    ):
        known = [v for day in daily.values() if nonnegative_number(v := day.get(group, {}).get(field))]
        result[output] = {"mean": round(sum(known) / len(known), 6) if known else None,
                          "days_with_values": len(known), "days_in_period": days}
    return {"start": start.isoformat(), "end_inclusive": end.isoformat(), "timezone": timezone,
            "metrics": result}
