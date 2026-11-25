"""The standalone Open Health Toolkit command line."""
import argparse
from datetime import date
import json
import os
from pathlib import Path
import sqlite3
from subprocess import CalledProcessError
import sys
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import catalog, diary, documents, nutrition, nutri_score, oura


def parser():
    app = argparse.ArgumentParser(description=__doc__)
    app.add_argument("--catalog", type=Path, help="Private JSONL file with user- food IDs")
    app.add_argument("--diary", type=Path, default=Path.home() / ".local/share/open-health-toolkit/diary.sqlite")
    commands = app.add_subparsers(dest="command", required=True)

    find = commands.add_parser("find", help="Search the reference or private catalog")
    find.add_argument("query")
    find.add_argument("--kind", choices=nutrition.PROFILE_KINDS)
    find.add_argument("--limit", type=int, default=10)
    find.add_argument("--personal", action="store_true")
    commands.add_parser("get").add_argument("id")

    for name in ("calculate", "assess-portion", "nutri-score", "energy-eu", "energy-requirements"):
        commands.add_parser(name).add_argument("--json", required=True)

    log = commands.add_parser("log", help="Save a confirmed portion to the local diary")
    log.add_argument("--id", required=True)
    log.add_argument("--day", type=date.fromisoformat, required=True)
    log.add_argument("--json", required=True)
    log.add_argument("--dry-run", action="store_true")
    report = commands.add_parser("report", help="Summarize recorded nutrients and coverage")
    report.add_argument("--end", type=date.fromisoformat, required=True)
    report.add_argument("--days", choices=(7, 28), type=int, required=True)

    process = commands.add_parser("pdf-extract", help="Create a local page-text and image bundle")
    process.add_argument("pdf", type=Path)
    process.add_argument("bundle", type=Path)
    process.add_argument("--ocr-language", help="Use Tesseract on pages without embedded text")
    export = commands.add_parser("pdf-markdown", help="Export a PDF bundle as page-linked Markdown")
    export.add_argument("bundle", type=Path)
    export.add_argument("--title", required=True)

    normalize = commands.add_parser("oura-normalize", help="Minimize a user-supplied JSON array")
    normalize.add_argument("collection", choices=sorted(oura.COLLECTIONS))
    normalize.add_argument("input_file", type=Path)
    normalize.add_argument("--timezone", default="UTC")
    normalize.add_argument("--output", type=Path, required=True)
    fetch = commands.add_parser("oura-fetch", help="Fetch an authorized Oura collection into a local file")
    fetch.add_argument("collection", choices=sorted(oura.COLLECTIONS))
    fetch.add_argument("--start", type=date.fromisoformat, required=True)
    fetch.add_argument("--end", type=date.fromisoformat, required=True, help="Exclusive")
    fetch.add_argument("--timezone", default="UTC")
    fetch.add_argument("--output", type=Path, required=True)
    overview = commands.add_parser("oura-report", help="Summarize daily activity and main sleep coverage")
    overview.add_argument("bundles", type=Path, nargs="+")
    overview.add_argument("--end", type=date.fromisoformat, required=True)
    overview.add_argument("--days", choices=(7, 28), type=int, required=True)
    return app


def write_private(output, result):
    encoded = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(encoded)
    return {"output": str(output), "records": len(result["records"])}


def execute(args):
    command = args.command
    if command == "report":
        return diary.report(args.diary, args.end, args.days)
    if command == "oura-report":
        bundles = [json.loads(path.read_text(encoding="utf-8")) for path in args.bundles]
        return oura.report(bundles, args.end, args.days)
    if command == "pdf-extract":
        return documents.extract(args.pdf, args.bundle, ocr_language=args.ocr_language)
    if command == "pdf-markdown":
        return {"files": documents.export_markdown(args.bundle, args.title)}
    if command in ("oura-normalize", "oura-fetch"):
        ZoneInfo(args.timezone)
        if command == "oura-normalize":
            records = json.loads(args.input_file.read_text(encoding="utf-8"))
            result = {"collection": args.collection, "timezone": args.timezone,
                      "records": oura.normalize(args.collection, records, args.timezone)}
        else:
            result = oura.fetch(args.collection, args.start, args.end, args.timezone, os.getenv("OURA_ACCESS_TOKEN"))
        return write_private(args.output, result)

    personal = catalog.user_rows(args.catalog)
    if command == "find":
        return catalog.find(args.query, kind=args.kind, limit=args.limit, personal=personal if args.personal else None)
    if command == "get":
        return catalog.get(args.id, personal)[0]
    request = json.loads(args.json)
    if command == "nutri-score":
        cards = {}
        if isinstance(request, dict) and isinstance(request.get("food_id"), str):
            cards[request["food_id"]] = catalog.get(request["food_id"], personal)[0]
        return nutri_score.evaluate(request, cards)
    if command == "energy-eu":
        return nutrition.energy_eu(request)
    if command == "energy-requirements":
        return nutrition.energy_requirements(request)
    if command == "assess-portion":
        if not isinstance(request, dict) or request.keys() != {"portion", "goal"}:
            raise ValueError("Supply portion and goal")
        return nutrition.assess_portion(catalog.calculate(request["portion"], personal), request["goal"])
    result = catalog.calculate(request, personal)
    if command == "log" and not args.dry_run:
        return diary.log(args.diary, args.id, args.day, request, result)
    return result


def main():
    args = parser().parse_args()
    try:
        result = execute(args)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    except CalledProcessError:
        print("PDF extraction or OCR failed", file=sys.stderr)
        return 1
    except (ValueError, OSError, RuntimeError, KeyError, TypeError, sqlite3.Error, ZoneInfoNotFoundError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
