# Nutri-Score

The toolkit implements the 2023 update from Santé publique France. Categories are explicit. The result includes the method version, grade, numeric score, point contributions and missing inputs when applicable. Qualifying water has grade A and a null numeric score. Dairy and plant-based drinks use beverage rules when they meet the official category definition.

Use the original declaration basis for the complete composition. Beverage inputs use `100ml`. Use the official rules for qualifying ingredients and percentages. A prepared recipe needs a composition and yield for the finished mixture. A partial portion of the same composition has the same grade. The grade describes a food's profile. Portion totals, personal priorities, micronutrients and period reports are available through their own methods.

```sh
health-toolkit nutri-score --json '{
  "category":"general",
  "basis":"100g",
  "values":{"energy_kj":360,"total_sugars_g":2.3,"saturated_fat_g":0.4,
            "salt_g":0.8,"protein_g":5,"fiber_g":3.8,"fruit_vegetable_legume_percent":45}
}'
health-toolkit --catalog examples/product.jsonl nutri-score --json '{
  "food_id":"user-example-soup",
  "assessment":{"category":"general","basis":"100g","fruit_vegetable_legume_percent":45},
  "source":"Synthetic example recipe"
}'
```

The supported categories are `general`, `red_meat`, `cheese`, `fats_oils_nuts_seeds`, `beverage` and `water`. Non-water beverages require a confirmed true or false for `non_nutritive_sweeteners`. A fats, oils, nuts or seeds score uses `fat_g` and derives energy from saturated fat. Energy in other categories comes from `energy_kj`. Supply salt in grams or sodium in milligrams on the same basis. The sodium conversion uses 2.5 g salt per gram of sodium. Use `fruit_vegetable_legume_percent` for the share determined under the method, including applicable oil rules.

The card path checks basis, unit and provenance. It excludes fields marked as estimates from analogues or unverified legacy entries. It returns `insufficient_data` with a list of missing inputs when a grade would rely on assumptions. Comparisons with source records are for personal or analytical use. The toolkit outputs text letters and ships no official label graphics.

The normative tables in the technical Q&A take priority at boundary discrepancies in the spreadsheet. For example, 3.2 g salt receives 15 points per the table threshold for 3.2 g, and the next point applies above 3.2 g. The project tests representative categories and exact cutoff behavior.

- [Official FAQ and point tables, pages 26–33](https://www.santepubliquefrance.fr/sites/default/files/rdd/document/FAQ-updatedAlgo-V11.pdf)
- [Official calculator and documents](https://www.santepubliquefrance.fr/en/nutrition-and-physical-activity/nutri-score)
- [Prospective study of the updated index, Deschasaux-Tanguy et al., 2024](https://doi.org/10.1016/j.lanepe.2024.101006)
