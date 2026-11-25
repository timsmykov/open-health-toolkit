# Agent tool instructions

Use the toolkit's JSON output as evidence. A useful answer gives amounts, units, missing fields, and source information.

## Nutrition

1. Read the user's current goal or ask for the relevant constraint if needed.
2. Search the correct dataset, open the exact food ID, and check food state, variant and package.
3. Select `calculate` for portion quantities, `assess-portion` for explicit criteria, or `nutri-score` for product composition. Use the recorded-period report for longer-term intake.
4. When a value is missing, return the missing field or partial coverage. Keep approximations, analytical measurements, and package declarations distinguishable.
5. Log only a confirmed eaten meal, and pass a stable action ID. Run `--dry-run` for an inspection.

To source a new user product, prefer the manufacturer's exact label and compare matching retailer entries where necessary. Preserve net package size, composition, measurement basis and evidence. Configure any browser or scraper as a separate deployment tool with explicit source and privacy boundaries.

## Health Analyst

Use Oura coverage and metric-specific notes when reporting wearable patterns. Use the page layout and image together for a reference table or graphic. For general medical explanations, check suitable primary or official sources. Examples include [WHO](https://www.who.int/), [NICE guidance](https://www.nice.org.uk/guidance), [Cochrane](https://www.cochranelibrary.com/) and [PubMed](https://pubmed.ncbi.nlm.nih.gov/). Treat search results as pointers to sources. A configured Chief of Staff can route requests and return tool results; its permissions should match the user's requested action.
