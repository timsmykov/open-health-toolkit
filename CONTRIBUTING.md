# Contributing

Open Health Toolkit uses Python 3.11 or newer. Keep source text, examples, command output and documentation in English. Use synthetic fixtures for health records, user catalogs and document tests.

## Repository layout

| Path | Purpose |
| --- | --- |
| `health_toolkit/catalog.py` and `health_toolkit/data/` | Food lookup, BLS snapshot, type labels and provenance |
| `health_toolkit/nutrition.py`, `nutri_score.py`, and `diary.py` within the package | Portion and recipe math, composition scores and recorded nutrient snapshots |
| `health_toolkit/oura*.py` | Oura API access, minimization and reporting |
| `health_toolkit/documents.py` | PDF layout, optional OCR and Markdown export |
| `health_toolkit/__main__.py` | Shared CLI entry point |
| `docs/` and `examples/` | Guides, architecture, agent interfaces and synthetic inputs |
| `tests/` | Offline tests and expected calculation results |

## Make and test a change

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
```

Install Poppler for the PDF integration test. Tesseract and a supported language pack allow a separate OCR check. Oura tests use mocked API responses. Run an installed CLI command from outside the checkout if you change package data or the entry point.

For a food source update, retain the source ID, release, basis, units and origin. Document the distribution license and required attribution before adding data. For a formula update, include the published method version and verify boundary cases against the reference. Keep examples and guides aligned with any command or schema change.

Keep credentials, journal databases, personalized inputs and PDF bundles in private storage. [Architecture and deployment boundaries](docs/architecture.md) · [Release checks](docs/release.md)
