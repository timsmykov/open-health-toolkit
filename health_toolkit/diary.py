"""Local SQLite diary with immutable, replayable nutrient snapshots."""
from contextlib import closing
from datetime import timedelta
import json
import os
from pathlib import Path
import sqlite3

from . import nutrition


def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    try:
        os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
    except FileExistsError:
        pass
    db = sqlite3.connect(path)
    db.execute("""CREATE TABLE IF NOT EXISTS meals
                  (id TEXT PRIMARY KEY, date TEXT NOT NULL, payload TEXT NOT NULL)""")
    return db


def log(path, entry_id, day, portion, calculation):
    if not entry_id.strip():
        raise ValueError("Supply a stable ID for the meal entry")
    record = {"id": entry_id, "date": day.isoformat(), "portion": portion,
              "method": calculation["method"], "nutrient_amounts": calculation["nutrients"],
              "nutrient_coverage": calculation.get("coverage", {})}
    data = json.dumps(record, sort_keys=True, allow_nan=False)
    with closing(connect(path)) as db, db:
        db.execute("INSERT OR IGNORE INTO meals VALUES (?, ?, ?)", (entry_id, day.isoformat(), data))
        saved = json.loads(db.execute("SELECT payload FROM meals WHERE id = ?", (entry_id,)).fetchone()[0])
        if saved["date"] != record["date"] or saved["portion"] != record["portion"]:
            raise ValueError("The meal entry ID already refers to a different portion")
    return saved


def report(path, end, days):
    """Return recorded-day totals with coverage. End is inclusive."""
    if days not in (7, 28):
        raise ValueError("Choose a 7 or 28 day period")
    begin = end - timedelta(days=days - 1)
    records = []
    if Path(path).is_file():
        with closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)) as db:
            records = [(day, json.loads(payload)) for day, payload in db.execute(
                "SELECT date, payload FROM meals WHERE date BETWEEN ? AND ? ORDER BY date, id",
                (begin.isoformat(), end.isoformat()))]
    dates = {day for day, _ in records}
    return {"start": begin.isoformat(), "end_inclusive": end.isoformat(), "days": days,
            "days_with_entries": len(dates), "days_without_entries": days - len(dates),
            "entries": len(records), "nutrients": nutrition.summarize(records)}
