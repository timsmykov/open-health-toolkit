# BLS 4.0 data attribution

Max Rubner-Institut (2025). *German Nutrient Database (Bundeslebensmittelschlüssel), version 4.0*. Karlsruhe. [DOI 10.25826/Data20251217-134202-0](https://doi.org/10.25826/Data20251217-134202-0).

The underlying data in `foods.jsonl.gz` and component metadata in `source.json` are distributed under [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/). Download and edition information are available from the [publisher](https://blsdb.de/download).

This adaptation selects the original English names, normalizes whitespace and unit symbols, translates method and status labels into English and packages the records as gzip JSON Lines. Source worksheet rows and component codes are preserved. The source database includes analytical values, recipes, calculated values and other methods. Its authorship does not imply endorsement of this toolkit.

The separate `bls-labels.json` file contains project annotations keyed by public BLS codes. The English names and numbers come from BLS itself. This bundle contains no nutrient values from the closed deployment's supplements.
