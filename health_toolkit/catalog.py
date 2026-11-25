"""Search the English BLS 4.0 reference and load isolated user catalogs."""
import gzip
import json
import re
from importlib.resources import files

from . import nutrition

DATA = files("health_toolkit").joinpath("data")
COMPONENTS = {
    "ENERCJ": "energy_kj", "ENERCC": "kcal", "PROT625": "protein_g", "FAT": "fat_g",
    "CHO": "available_carbs_g", "FIBT": "fiber_g", "WATER": "water_g",
    "ALC": "alcohol_g", "POLYL": "polyols_g", "SUGAR": "total_sugars_g",
    "STARCH": "starch_g", "FASAT": "saturated_fat_g", "FAMS": "mufa_g",
    "FAPU": "pufa_g", "F18:3CN3": "ala_g", "F18:2CN6": "la_g",
    "F20:5CN3": "epa_g", "F22:5CN3": "dpa_g", "F22:6CN3": "dha_g",
    "NACL": "salt_g", "NA": "sodium_mg", "K": "potassium_mg",
    "CA": "calcium_mg", "MG": "magnesium_mg", "P": "phosphorus_mg",
    "CLD": "chloride_mg", "FE": "iron_mg", "ZN": "zinc_mg", "CU": "copper_mg",
    "MN": "manganese_mg", "CHORL": "cholesterol_mg", "VITC": "vitamin_c_mg",
    "VITE": "vitamin_e_mg", "THIA": "b1_mg", "RIBF": "b2_mg", "NIA": "b3_mg",
    "PANTAC": "b5_mg", "VITB6": "b6_mg", "FD": "fluoride_mg",
    "VITAA": "vitamin_a_rae_ug", "VITD": "vitamin_d_ug", "VITK": "vitamin_k_ug",
    "BIOT": "biotin_ug", "FOLFD": "folate_ug", "FOL": "folate_dfe_ug", "VITB12": "b12_ug",
    "CR": "chromium_ug", "MO": "molybdenum_ug", "SE": "selenium_ug",
}


def tokens(text):
    return re.findall(r"[^\W_]+", text.casefold())


def source_rows():
    with DATA.joinpath("foods.jsonl.gz").open("rb") as packed, gzip.open(packed, "rt", encoding="utf-8") as source:
        for line in source:
            yield json.loads(line)


def user_rows(path):
    if path is None:
        return {}
    result = {}
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            if (not isinstance(row, dict) or not isinstance(row.get("id"), str)
                    or not row["id"].startswith("user-") or row["id"] in result
                    or not isinstance(row.get("title"), str) or not isinstance(row.get("nutrients"), dict)):
                raise ValueError("User cards require a unique user- ID, title and nutrients")
            if row.get("profile_kind", "unresolved") not in nutrition.PROFILE_KINDS:
                raise ValueError("Invalid food profile kind")
            result[row["id"]] = {**row, "properties": row.get("properties", {})}
    return result


def find(query, *, kind=None, limit=10, personal=None):
    words = tokens(query)
    if not words or not 1 <= limit <= 100:
        raise ValueError("Supply a search term and a limit from 1 to 100")
    labels = json.loads(DATA.joinpath("bls-labels.json").read_text(encoding="utf-8"))
    matches = []
    if personal is None:
        candidates = (("bls-" + code, title, labels.get(code, "unresolved"))
                      for code, title, _, _ in source_rows())
    else:
        candidates = ((r["id"], r["title"], r.get("profile_kind", "unresolved")) for r in personal.values())
    for food_id, title, label in candidates:
        if kind and label != kind:
            continue
        name = tokens(title)
        exact_id = tokens(food_id) == words or (food_id.startswith("bls-") and tokens(food_id[4:]) == words)
        exact_title = name == words
        if exact_id or set(words) <= set(name):
            matches.append(((exact_id, exact_title, len(name) * -1),
                            {"id": food_id, "title": title, "profile_kind": label}))
    return [entry for _, entry in sorted(matches, key=lambda match: match[0], reverse=True)[:limit]]


def get(food_id, personal):
    if food_id.startswith("user-"):
        if food_id not in personal:
            raise ValueError("User food ID not found")
        return personal[food_id], "products"
    code = food_id.upper().removeprefix("BLS-")
    record = next((row for row in source_rows() if row[0] == code), None)
    if record is None:
        raise ValueError("BLS food ID not found")
    _, title, source_row, values = record
    meta = json.loads(DATA.joinpath("source.json").read_text(encoding="utf-8"))
    labels = json.loads(DATA.joinpath("bls-labels.json").read_text(encoding="utf-8"))
    nutrients, original = {}, {}
    for (component, info), (value, method, reference) in zip(meta["components"].items(), values, strict=True):
        spec = {**info, "basis": "100g", "method": method, "reference_in_original": reference}
        original[component] = {**spec, "value" if nutrition.known(value) else "status": value}
        if nutrition.known(value) and (key := COMPONENTS.get(component)):
            amount = nutrition.canonical_amount(key, value, info["unit"])
            nutrients[key] = {"value": float(amount), "unit": nutrition.UNITS[key], "basis": "100g",
                              "source": meta["doi"], "method": f"bls_{method}", "source_component": component,
                              "source_row": source_row, "source_version": meta["version"], "food_state": title}
    return {"id": "bls-" + code, "title": title, "profile_kind": labels.get(code, "unresolved"),
            "source_url": meta["doi"], "properties": {}, "nutrients": nutrients,
            "source_nutrients": original}, "reference"


def calculate(payload, personal):
    if not isinstance(payload, dict):
        raise ValueError("Portion requires a JSON object")

    def load(item):
        if not isinstance(item, dict) or not isinstance(item.get("food_id"), str):
            raise ValueError("A portion or recipe component requires a food_id")
        return get(item["food_id"], personal)

    if "recipe_components" in payload:
        if payload.keys() - {"recipe_components", "finished_grams", "eaten_grams"}:
            raise ValueError("Specify recipe components, finished yield and optional portion")
        values, coverage = nutrition.recipe_values(payload["recipe_components"], load,
                                                   payload.get("finished_grams"), payload.get("eaten_grams"))
        return {"method": nutrition.VERSION, "nutrients": nutrition.serialize(values), "coverage": coverage}
    if payload.keys() - {"food_id", "grams", "ml", "serving_fraction"}:
        raise ValueError("Specify a food_id and optional quantity")
    row, dataset = load(payload)
    amount, basis = nutrition.prepare_amount(payload, row, use_package=dataset == "products")
    if not amount:
        raise ValueError("Supply grams or ml, or use a confirmed package or serving")
    return {"method": nutrition.VERSION, "nutrients": nutrition.serialize(nutrition.portion_values(row, dataset, amount)),
            "food_id": row["id"], "portion_basis": basis, **{key: nutrition.output(value) for key, value in amount.items()}}
