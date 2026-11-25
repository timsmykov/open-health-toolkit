# Nutrition

The reference holds 7,140 food profiles with the English names published by the Max Rubner-Institut and 138 source components. Curated type annotations cover 352 BLS IDs, including 289 ingredients. The remaining food types are unresolved in this toolkit. Use `find --kind ingredient` for the curated ingredient set or omit the filter for expanded search. Check the food's state, such as raw, dried, cooked or fortified, before using a match. [Source and attribution](../health_toolkit/data/ATTRIBUTION.md)

## Own catalog

Store your catalog outside the repository in UTF-8 JSON Lines. Each entry needs a unique `user-` ID, `title`, `profile_kind`, `properties`, and `nutrients`. See the [synthetic product example](../examples/product.jsonl).

A nutrient includes `value`, `unit`, `basis`, `method` and `source`. Supported bases are `100g`, `100ml`, `serving_g` and `serving_ml`. Serving-based data also require `basis_amount`. When an item has a measured density, set the top-level `density` object to `{"g_per_ml": ..., "source": "..."}`. Omit unknown values and represent confirmed zeros explicitly. Keep available carbohydrates, total carbohydrates, total sugars and added sugars as distinct fields.

```sh
health-toolkit --catalog examples/product.jsonl find soup --personal
health-toolkit --catalog examples/product.jsonl get user-example-soup
health-toolkit get bls-G541100
```

## Portions, recipes and goals

Supply `grams`, `ml` or `serving_fraction`. With a user product and a known package size, one unspecified portion uses that package. The `calculate` command returns sourced quantities. A recipe takes `recipe_components` as an array of portion objects. For a partial recipe use `finished_grams` and `eaten_grams`. Components default to the form as eaten. For a raw-to-cooked recipe, set `state` to `raw_cooked` and supply any `retention` factors by nutrient key and a `retention_source`. Check per-nutrient coverage before interpreting an incomplete recipe.

```sh
health-toolkit assess-portion --json '{
  "portion": {"food_id":"bls-C133000","grams":60},
  "goal": {"id":"higher-fiber-example","method":"portion_targets_v1",
           "targets":{"fiber_g":{"min":4}}}
}'
```

The threshold above is a demonstration. The goal is an input and may be selected by each caller. Each criterion picks a nutrient and inclusive minimum, maximum or both in that nutrient's canonical unit. The response includes `below_min`, `above_max`, `within_target` or `unknown`, its source, and recipe coverage when applicable. [Nutri-Score](nutri-score.md) is available independently of goal assessment.

## Diary and reports

```sh
health-toolkit --diary "$PWD/outputs/demo.sqlite" log --id demo-01 --day 2000-01-02 \
  --json '{"food_id":"bls-C133000","grams":60}' --dry-run
health-toolkit --diary "$PWD/outputs/demo.sqlite" log --id demo-01 --day 2000-01-02 \
  --json '{"food_id":"bls-C133000","grams":60}'
health-toolkit --diary "$PWD/outputs/demo.sqlite" report --end 2000-01-07 --days 7
```

Use one private diary per installation or user. Each entry saves the calculation snapshot. Replaying its ID, date and portion returns the original snapshot. A conflicting reuse of an ID is rejected. Reports use an inclusive ending date and track recorded days and missing nutrients. Use the same ending date for nutrition and Oura. The current diary exposes explicit logging and read-only reports. A record-amend workflow with revision history is a future integration feature.
