# Food data and provenance

The bundled composition data come from version 4.0 of the German Nutrient Database (BLS), published by the Max Rubner-Institut. The project uses the English names, preserves BLS IDs and worksheet rows, and normalizes labels and units for use in code. [Source and license](../health_toolkit/data/ATTRIBUTION.md)

| Collection | Size | What each entry represents |
| --- | ---: | --- |
| BLS reference | 7,140 | A published food composition profile in a specific form, including raw foods, cooked variants and prepared dishes |
| Toolkit classification | 352 | Type annotations attached to BLS IDs, including 289 `ingredient` and 63 `prepared` entries |
| User catalog | Per installation | Products, retailer variants and foods the user enters with their own evidence |

The remaining 6,788 BLS profiles have `profile_kind: unresolved` in the toolkit. The type describes the food form. Nutrient measurements, estimates and missing values have separate source metadata.

## An example of a food and its preparation variants

| ID | English source title | Toolkit type |
| --- | --- | --- |
| `bls-G541100` | Sweet pepper green, raw | `ingredient` |
| `bls-G541072` | Sweet pepper green, grilled | `unresolved` |
| `bls-G541032` | Sweet pepper green, boiled | `unresolved` |

```sh
health-toolkit find 'green sweet pepper'
health-toolkit find 'green sweet pepper' --kind ingredient
health-toolkit get bls-G541100
```

## Card fields

The `get` response includes the English `title`, stable `id`, `profile_kind`, `source_url` and `nutrients`. Each normalized numeric value carries its unit, basis, method, version and origin. BLS cards also include `source_nutrients` with the 138 source components. A component can hold a numeric value or a status such as missing, trace, below detection or below quantification. Numerical coverage varies by food and component. Confirmed zeros are stored as numbers.

The full source dataset is shipped in compressed JSON Lines. Each line stores the BLS code, English food name, source worksheet row and components in the order given by `source.json`. Each component stores its value or status, method, and a flag indicating whether the original worksheet includes a reference. The separate `bls-labels.json` maps public BLS IDs to toolkit types.

For a packaged brand, keep the manufacturer or retailer version, net amount and label evidence in your own catalog. Use BLS when the food and preparation actually match. See the [user catalog schema and calculation guide](nutrition.md#own-catalog).
