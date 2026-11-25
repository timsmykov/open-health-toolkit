"""Package user-provided PDFs with stable page citations and page imagery."""
from collections import defaultdict
import csv
from hashlib import file_digest
from io import StringIO
import json
from pathlib import Path
from shutil import which
from subprocess import run
from tempfile import TemporaryDirectory
from xml.etree import ElementTree


def ocr(image, language, scale):
    result = run(["tesseract", str(image), "stdout", "-l", language, "tsv"],
                 check=True, capture_output=True, text=True)
    groups = defaultdict(list)
    for row in csv.DictReader(StringIO(result.stdout), delimiter="\t"):
        if row["level"] == "5" and (row.get("text") or "").strip():
            groups[row["block_num"]].append(row)
    blocks = []
    for words in groups.values():
        lines = defaultdict(list)
        left, top, right, bottom = [], [], [], []
        for word in words:
            lines[(word["par_num"], word["line_num"])].append(word["text"])
            left.append(int(word["left"]))
            top.append(int(word["top"]))
            right.append(left[-1] + int(word["width"]))
            bottom.append(top[-1] + int(word["height"]))
        blocks.append({"text": "\n".join(" ".join(line) for line in lines.values()),
                       "bbox": [round(value * scale, 2)
                                for value in (min(left), min(top), max(right), max(bottom))]})
    return blocks


def extract(pdf, output, *, ocr_language=None):
    if not which("pdftotext") or not which("pdftoppm"):
        raise RuntimeError("Install Poppler utilities (pdftotext and pdftoppm)")
    if ocr_language and not which("tesseract"):
        raise RuntimeError("Install Tesseract with the requested language pack")
    pdf, output = pdf.resolve(strict=True), output.resolve()
    with pdf.open("rb") as stream:
        digest = file_digest(stream, "sha256").hexdigest()
    if output.exists():
        raise ValueError("Choose a new output directory for this document bundle")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".document-", dir=output.parent) as stage:
        bundle = Path(stage) / "bundle"
        bundle.mkdir(mode=0o700)
        xml = run(["pdftotext", "-bbox-layout", str(pdf), "-"], capture_output=True, check=True).stdout
        root = ElementTree.fromstring(xml)
        pages = []
        for number, page in enumerate(root.findall(".//{*}page"), 1):
            stem = f"page-{number:04d}"
            image, layout = stem + ".png", stem + ".json"
            run(["pdftoppm", "-f", str(number), "-l", str(number), "-r", "125", "-png", "-singlefile",
                 str(pdf), str(bundle / stem)], check=True, capture_output=True)
            blocks = []
            for block in page.findall(".//{*}block"):
                lines = [" ".join(word.text or "" for word in line.findall("{*}word"))
                         for line in block.findall("{*}line")]
                text = "\n".join(lines).strip()
                if text:
                    blocks.append({"text": text, "bbox": [float(block.attrib[k]) for k in
                                                          ("xMin", "yMin", "xMax", "yMax")]})
            status = "embedded_text" if blocks else "ocr_required"
            if not blocks and ocr_language:
                blocks = ocr(bundle / image, ocr_language, 72 / 125)
                status = "ocr_text" if blocks else "ocr_empty"
            record = {"pdf_page": number, "width_pt": float(page.attrib["width"]),
                      "height_pt": float(page.attrib["height"]), "page_image": image, "layout": layout,
                      "text_status": status, "blocks": blocks}
            (bundle / layout).write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
            pages.append({key: value for key, value in record.items() if key != "blocks"})
        if not pages:
            raise ValueError("The PDF has no readable page metadata")
        manifest = {"source_sha256": digest, "pages": pages}
        (bundle / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        bundle.rename(output)
        return manifest


def export_markdown(bundle, title):
    """Write pages with searchable chunks and in-bundle image references."""
    if not title or not title.strip() or "\n" in title or "\r" in title:
        raise ValueError("Pass a single-line document title")
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    written = []
    for entry in manifest["pages"]:
        page = entry["pdf_page"]
        if type(page) is not int or page < 1:
            raise ValueError("Invalid PDF page number")
        stem = f"page-{page:04d}"
        layout = json.loads((bundle / (stem + ".json")).read_text(encoding="utf-8"))
        image = stem + ".png"
        if not (bundle / image).is_file() or layout["pdf_page"] != page:
            raise ValueError("Page image or layout is missing")
        lines = [f"# {title} · PDF page {page}", "", f"Source SHA-256: `{manifest['source_sha256']}`",
                 "", f"![PDF page {page}]({image})", ""]
        if not layout["blocks"]:
            lines.extend(("No searchable text. Review the page image.", ""))
        for index, block in enumerate(layout["blocks"], 1):
            lines.extend((f"## Block {index}", "", block["text"], ""))
        path = bundle / (stem + ".md")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        written.append(path.name)
    return written
