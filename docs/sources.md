# Oura and illustrated references

## Oura

Start with the synthetic example. All fetch windows are half-open, with an exclusive end. Date summaries use an inclusive end. Choose the same local timezone and reporting dates for each source.

```sh
health-toolkit oura-normalize heartrate examples/oura-heart-rate.json \
  --timezone UTC --output outputs/example-hourly.json
```

For live access, obtain an OAuth access token for your authorized Oura scopes and supply it through the process environment as `OURA_ACCESS_TOKEN`. The toolkit reads collections and writes a new local file. It does not manage OAuth consent or refresh. [Oura API v2 docs](https://cloud.ouraring.com/v2/docs)

```sh
health-toolkit oura-fetch sleep --start 2000-01-01 --end 2000-01-08 \
  --timezone UTC --output outputs/sleep.json
health-toolkit oura-fetch daily_activity --start 2000-01-01 --end 2000-01-08 \
  --timezone UTC --output outputs/activity.json
health-toolkit oura-report outputs/sleep.json outputs/activity.json --end 2000-01-07 --days 7
```

The dates above illustrate the interface. The collection client has pagination, date filtering, bounded retries and window splitting for timed series. Stored heart-rate samples are hourly means with sample counts. Battery data aggregate by date. In other collections, recognized high-frequency sample windows aggregate hourly and known motion/phase series are dropped. The sleep summary chooses the longest `long_sleep` for each Oura day. It keeps lowest and average heart rate distinct and reports missing-day coverage.

## PDF reference workflow

Install Poppler to get `pdftotext` and `pdftoppm`. For scanned pages install Tesseract and the required language pack.

```sh
health-toolkit pdf-extract /path/to/your/reference.pdf outputs/reference --ocr-language eng
health-toolkit pdf-markdown outputs/reference --title 'Example reference'
```

The bundle contains a manifest, layout JSON and a full-page image for every page. Text blocks have coordinates and are associated with the PDF page and an SHA-256 of the source. Optional OCR handles pages with no embedded text. Review figures and mixed text/image pages visually. The complete page render retains tables, vector diagrams, and embedded images in their original visual context. The Markdown export preserves a page-local link to the render. Keep the bundle together when indexing it.

To use a private G-Brain instance, import the Markdown files into your own source and make the corresponding PNGs accessible to the model through your artifact store. For each result, read both the text and its page render when a diagram or table carries evidence. Automatic upload, source access checks, and multimodal search depend on your deployment. This repository ships no source books, extracts from third-party books, or private records.
