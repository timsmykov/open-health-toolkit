# Open Health Toolkit

A local Python toolkit for food composition, nutrition calculations, Oura exports and illustrated health references. Its calculations can run from the command line or behind an agent. The included example product and telemetry are synthetic.

![Open Health Toolkit architecture](docs/architecture.png)

## Quick start

Requires Python 3.11 or newer. The core uses the standard library.

```sh
git clone https://github.com/timsmykov/open-health-toolkit.git
cd open-health-toolkit
python -m venv .venv
. .venv/bin/activate
python -m pip install .
health-toolkit find 'green sweet pepper' --kind ingredient
health-toolkit calculate --json '{"food_id":"bls-G541100","grams":75}'
health-toolkit --catalog examples/product.jsonl calculate \
  --json '{"food_id":"user-example-soup","serving_fraction":0.5}'
```

For use without installing, replace `health-toolkit` with `python -m health_toolkit` from the repository root. Put global options such as `--catalog` and `--diary` before the subcommand.

## Components

| Component | What you can run |
| --- | --- |
| Food reference and user catalog | English BLS 4.0 lookup, source records, explicit food types, a separate local product file |
| Nutrition | Portion and recipe maths, explicit goal assessment, Nutri-Score, an SQLite diary and 7/28-day nutrition summaries |
| Oura | API v2 reading with your access token, local normalization and 7/28-day coverage summaries |
| Illustrated references | PDF text and coordinates, page images, optional OCR, Markdown with page references |
| Agents and retrieval | English tool instructions for an optional OpenBot or G-Brain integration |

## Food data at a glance

The toolkit bundles the complete English-language BLS 4.0 reference snapshot of **7,140 food profiles**. A profile represents a particular food or preparation. Raw, boiled and grilled green peppers have separate source IDs. The toolkit adds type annotations for **352** BLS entries, including **289 ingredients**. Use `--kind ingredient` to limit lookup to those 289. Your store products and recipes go in your own catalog. [Food data guide](docs/food-data.md)

## Documentation

- [Nutrition quick start and input contracts](docs/nutrition.md)
- [Nutri-Score method and evidence](docs/nutri-score.md)
- [Oura and document setup](docs/sources.md)
- [Architecture, agent integration and deployment boundaries](docs/architecture.md)
- [Food data, field definitions and provenance](docs/food-data.md)
- [Contribution guide and repository layout](CONTRIBUTING.md)
- [Release checks](docs/release.md)

## Verification

```sh
python -m unittest discover -s tests -v
```

Install Poppler for the PDF integration test. Tesseract is optional at runtime and requires the requested language data. Oura tests use synthetic responses.

Code and documentation are under the [MIT license](LICENSE). The bundled BLS data are under [CC BY 4.0, with attribution and transformation details](health_toolkit/data/ATTRIBUTION.md).
