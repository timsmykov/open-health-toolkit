"""Versioned calculation rules shared by the diary, catalog and period reports."""
from collections import defaultdict
from decimal import Decimal
import math

VERSION = "nutrition-v1"
MACROS = ("kcal", "protein_g", "fat_g", "carbs_g")
SERVING_GRAMS = "serving_g"
PACKAGE_FIELDS = {"grams": "package_g", "ml": "package_ml"}
PROFILE_KINDS = ("ingredient", "prepared", "unresolved")
UNITS = dict.fromkeys((
    "protein_g", "fat_g", "carbs_g", "available_carbs_g", "available_carbs_excluding_polyols_g", "fiber_g",
    "total_sugars_g", "added_sugars_g",
    "free_sugars_g", "starch_g", "saturated_fat_g", "trans_fat_g", "mufa_g", "pufa_g",
    "ala_g", "la_g", "epa_g", "dpa_g", "dha_g", "epa_dha_g", "salt_g", "water_g", "alcohol_g", "polyols_g",
), "g")
UNITS.update(dict.fromkeys((
    "sodium_mg", "potassium_mg", "calcium_mg", "magnesium_mg", "phosphorus_mg", "chloride_mg",
    "iron_mg", "zinc_mg", "copper_mg", "manganese_mg", "cholesterol_mg", "vitamin_c_mg",
    "vitamin_e_mg", "b1_mg", "b2_mg", "b3_mg", "b5_mg", "b6_mg", "choline_mg", "caffeine_mg", "fluoride_mg",
), "mg"))
UNITS.update(dict.fromkeys((
    "vitamin_a_rae_ug", "vitamin_d_ug", "vitamin_k_ug", "biotin_ug", "folate_ug",
    "folate_dfe_ug", "b12_ug", "selenium_ug", "iodine_ug", "chromium_ug", "molybdenum_ug",
), "ug"))
UNITS.update(kcal="kcal", energy_kj="kJ")
MASS = {"g": Decimal(1), "mg": Decimal("0.001"), "ug": Decimal("0.000001")}
BASIS = {"100g": "grams", "100ml": "ml", "serving_g": "grams", "serving_ml": "ml"}
ADULT_EER = {
    "male": {"inactive": (753.07, -10.83, 6.50, 14.10), "low_active": (581.47, -10.83, 8.30, 14.94),
             "active": (1004.82, -10.83, 6.52, 15.91), "very_active": (-517.88, -10.83, 15.61, 19.11)},
    "female": {"inactive": (584.90, -7.01, 5.72, 11.71), "low_active": (575.77, -7.01, 6.60, 12.14),
               "active": (710.25, -7.01, 6.54, 12.34), "very_active": (511.83, -7.01, 9.07, 12.56)},
}
ENERGY_SHARES = {"protein_g": 4, "fat_g": 9, "available_carbs_excluding_polyols_g": 4, "free_sugars_g": 4,
                 "saturated_fat_g": 9, "trans_fat_g": 9}


def known(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def numeric(value, name, positive=False):
    if not known(value) or (positive and not value):
        raise ValueError(f"{name}: expected a finite {'positive' if positive else 'nonnegative'} number")
    return Decimal(str(value))


def canonical_amount(key, value, unit):
    if key not in UNITS:
        raise ValueError(f"Unknown nutrient: {key}")
    amount = numeric(value, key)
    target = UNITS[key]
    if unit == target:
        return amount
    if unit in MASS and target in MASS:
        return amount * MASS[unit] / MASS[target]
    if unit == "kJ" and target == "kcal":
        return amount / Decimal("4.184")
    raise ValueError(f"{key}: incompatible units {unit} and {target}")


def profile(row, dataset):
    return row["nutrients"]


def prepare_amount(item, row, *, use_package=False):
    grams, ml = item.get("grams"), item.get("ml")
    fraction = item.get("serving_fraction")
    if sum(value is not None for value in (grams, ml, fraction)) > 1:
        raise ValueError("Choose one amount: grams, ml or serving_fraction")
    if grams is not None:
        return {"grams": numeric(grams, "grams", True)}, "reported"
    if ml is not None:
        return {"ml": numeric(ml, "ml", True)}, "reported"
    scale = numeric(1 if fraction is None else fraction, "serving_fraction", True)
    props = row["properties"]
    if use_package:
        package = {unit: numeric(props[field], field, True) * scale
                   for unit, field in PACKAGE_FIELDS.items() if props.get(field) is not None}
        if package:
            return package, "package_serving"
    if (portion := props.get(SERVING_GRAMS)) is not None:
        return {"grams": numeric(portion, SERVING_GRAMS, True) * scale}, "confirmed_standard_serving"
    if fraction is not None:
        raise ValueError("A fraction requires a known package size or standard serving")
    return {}, "unknown"


def portion_values(row, dataset, amount):
    quantities = dict(amount)
    density = row.get("density")
    if density is not None:
        if not density.get("source"):
            raise ValueError("Density requires a source")
        value = numeric(density.get("g_per_ml"), "g_per_ml", True)
        if "ml" in amount and "grams" not in amount:
            quantities["grams"] = quantities["ml"] * value
        if "grams" in amount and "ml" not in amount:
            quantities["ml"] = quantities["grams"] / value
    results = {}
    for key, spec in profile(row, dataset).items():
        basis = spec.get("basis")
        if basis not in BASIS or not spec.get("source"):
            raise ValueError(f"{key}: basis and source are required")
        denominator = numeric(spec.get("basis_amount"), "basis_amount", True) if basis.startswith("serving_") else 100
        normalized = canonical_amount(key, spec["value"], spec["unit"])
        quantity = quantities.get(BASIS[basis])
        if quantity is not None:
            results[key] = (normalized * quantity / denominator, {**spec, "card_id": row["id"],
                            **({"density": density} if BASIS[basis] not in amount else {})})
    if "sodium_mg" in results and "salt_g" not in results:
        value, source = results["sodium_mg"]
        results["salt_g"] = (value * Decimal("0.0025"), {**source, "derivation": "sodium_times_2_5"})
    if "salt_g" in results and "sodium_mg" not in results:
        value, source = results["salt_g"]
        results["sodium_mg"] = (value * 400, {**source, "derivation": "salt_divided_by_2_5"})
    if "epa_g" in results and "dha_g" in results and "epa_dha_g" not in results:
        epa, epa_source = results["epa_g"]
        dha, dha_source = results["dha_g"]
        results["epa_dha_g"] = (epa + dha, {"method": "epa_plus_dha", "inputs": [epa_source, dha_source]})
    return results


def recipe_values(components, load, finished_grams=None, eaten_grams=None):
    if not isinstance(components, list) or not components:
        raise ValueError("Specify recipe components")
    if eaten_grams is not None and finished_grams is None:
        raise ValueError("A recipe portion requires the finished yield in grams")
    ratio = Decimal(1)
    if finished_grams is not None:
        finished = numeric(finished_grams, "finished_grams", True)
        if eaten_grams is not None:
            ratio = numeric(eaten_grams, "eaten_grams", True) / finished
            if ratio > 1:
                raise ValueError("Portion exceeds the finished recipe yield")
    parts, totals, counts = [], defaultdict(Decimal), defaultdict(int)
    for item in components:
        row, dataset = load(item)
        amount, _ = prepare_amount(item, row, use_package=dataset == "products" and item.get("serving_fraction") is not None)
        if not amount:
            raise ValueError("Specify the amount for every component")
        state = item.get("state", "as_eaten")
        if state not in ("as_eaten", "raw_cooked"):
            raise ValueError("Component state must be as_eaten or raw_cooked")
        retained = item.get("retention", {})
        if not isinstance(retained, dict) or set(retained) - UNITS.keys():
            raise ValueError("Invalid retention factors")
        if retained and (state != "raw_cooked" or not item.get("retention_source")):
            raise ValueError("Retention factors require a raw input and a source")
        factors = {key: numeric(value, key) for key, value in retained.items()}
        if any(value > 1 for value in factors.values()):
            raise ValueError("Retention factors must be between 0 and 1")
        adjusted = {}
        for key, (value, source) in portion_values(row, dataset, amount).items():
            if state == "raw_cooked":
                if key not in factors:
                    continue
                value *= factors[key]
                source = {**source, "retention_source": item["retention_source"], "retention": retained[key]}
            adjusted[key] = (value * ratio, source)
            totals[key] += value * ratio
            counts[key] += 1
        parts.append({"card_id": row["id"], "nutrients": serialize(adjusted)})
    complete = {key: (value, {"method": "recipe_sum", "source": "recipe_components",
                              "inputs": [p["nutrients"][key]["source"] for p in parts]})
                for key, value in totals.items() if counts[key] == len(parts)}
    coverage = {key: {"known_sum": output(totals[key]) if counts[key] else None, "known_components": counts[key],
                      "components": len(parts)} for key in UNITS}
    return complete, coverage


def output(value):
    return float(round(value, 9))


def serialize(results):
    return {key: {"value": output(value), "unit": UNITS[key], "source": src}
            for key, (value, src) in results.items()}


def assess_portion(calculation, goal):
    """Compare a calculated portion with explicit, inclusive bounds in canonical units."""
    method = "portion_targets_v1"
    if (not isinstance(goal, dict) or set(goal) != {"id", "method", "targets"}
            or not isinstance(goal["id"], str) or not goal["id"].strip() or goal["method"] != method):
        raise ValueError("A goal must specify id, method=portion_targets_v1 and targets")
    targets = goal["targets"]
    if not isinstance(targets, dict) or not targets or targets.keys() - UNITS.keys():
        raise ValueError("Specify at least one target using a canonical nutrient ID")
    results = {}
    for key, bounds in targets.items():
        if not isinstance(bounds, dict) or not bounds or bounds.keys() - {"min", "max"}:
            raise ValueError(f"{key}: a target must specify min, max or both")
        minimum = numeric(bounds["min"], f"{key}.min") if "min" in bounds else Decimal(0)
        maximum = numeric(bounds["max"], f"{key}.max") if "max" in bounds else Decimal("Infinity")
        if minimum > maximum:
            raise ValueError(f"{key}: min exceeds max")
        datum = calculation["nutrients"].get(key)
        coverage = calculation.get("coverage", {}).get(key)
        if datum is None:
            status = "unknown"
        else:
            if datum["unit"] != UNITS[key]:
                raise ValueError(f"{key}: expected {UNITS[key]}")
            value = numeric(datum["value"], key)
            status = ("below_min" if value < minimum
                      else "above_max" if value > maximum else "within_target")
        results[key] = {"unit": UNITS[key], "target": bounds, "status": status, "observed": datum}
        if coverage is not None:
            results[key]["coverage"] = coverage
    return {"goal_id": goal["id"], "method": method, "calculation": calculation, "results": results}


def diary_amount(row, key):
    structured = row.get("nutrient_amounts", {}).get(key)
    if isinstance(structured, dict) and structured.get("unit") == UNITS[key] and known(structured.get("value")):
        return Decimal(str(structured["value"]))
    return None


def partial_diary_amount(row, key):
    coverage = row.get("nutrient_coverage", {}).get(key, {})
    if coverage.get("known_components", 0) and known(coverage.get("known_sum")):
        return Decimal(str(coverage["known_sum"]))
    return None


def summarize(entries, complete_days=(), excluded_from_mean=()):
    daily = defaultdict(list)
    for day, row in entries:
        daily[day].append(row)
    confirmed = set(complete_days)
    excluded = set(excluded_from_mean)
    totals = {}
    for key, unit in UNITS.items():
        values = [[diary_amount(row, key) for row in rows] for rows in daily.values()]
        present = [value for group in values for value in group if value is not None]
        partial = []
        for rows, group in zip(daily.values(), values):
            for row, value in zip(rows, group):
                if value is None and (subtotal := partial_diary_amount(row, key)) is not None:
                    partial.append(subtotal)
        days = {day: sum(group) for day, group in zip(daily, values)
                if day not in excluded and all(value is not None for value in group)}
        full = [value for day, value in days.items() if day in confirmed]
        totals[key] = {"unit": unit,
                       "known_sum": output(sum(present + partial, Decimal(0))) if present or partial else None,
                       "missing_rows": sum(len(group) for group in values) - len(present),
                       "partial_rows_with_known_contribution": len(partial),
                       "days_with_values_for_every_logged_item": len(days),
                       "mean_of_recorded_day_totals": output(sum(days.values()) / len(days)) if days else None,
                       "complete_days_with_values": len(full),
                       "mean_of_complete_day_totals": output(sum(full) / len(full)) if full else None}
    return totals


def energy_eu(payload):
    allowed = {"protein_g": 4, "fat_excluding_salatrims_g": 9, "available_carbs_excluding_polyols_g": 4, "fiber_g": 2,
               "other_polyols_g": 2.4, "erythritol_g": 0, "alcohol_g": 7, "organic_acids_g": 3, "salatrims_g": 6}
    if not isinstance(payload, dict) or payload.keys() != allowed.keys():
        raise ValueError("Supply every Annex XIV input, including confirmed zeros")
    result = sum(numeric(payload[key], key) * Decimal(str(factor)) for key, factor in allowed.items())
    return {"kcal": output(result), "method": "EU_1169_2011_Annex_XIV_estimate"}


def energy_requirements(payload):
    if not isinstance(payload, dict) or set(payload) != {"sex", "activity", "age_years", "height_cm", "weight_kg"}:
        raise ValueError("Supply sex, activity, age, height and weight")
    age, height, weight = (numeric(payload[k], k, True) for k in ("age_years", "height_cm", "weight_kg"))
    if age < 19 or not isinstance(payload["sex"], str) or not isinstance(payload["activity"], str):
        raise ValueError("The equation applies to adults aged 19 and over")
    factors = ADULT_EER.get(payload["sex"], {}).get(payload["activity"])
    if factors is None:
        raise ValueError("Select an explicit activity category and applicable group")
    result = sum(Decimal(str(x)) * y for x, y in zip(factors, (Decimal(1), age, height, weight)))
    return {"estimate_kcal_day": output(result), "method": "NASEM_2023_Table_5_17",
            "source": "https://www.nationalacademies.org/read/26818/chapter/7", "activity": payload["activity"]}


def period_shares(entries, complete_days):
    days = defaultdict(list)
    complete = set(complete_days)
    for day, row in entries:
        if day in complete:
            days[day].append(row)
    result = {}
    for key, factor in ENERGY_SHARES.items():
        paired = 0
        energy = total = Decimal(0)
        for rows in days.values():
            values = [(diary_amount(row, key), diary_amount(row, "kcal")) for row in rows]
            if all(n is not None and kcal is not None for n, kcal in values):
                daily_energy = sum(kcal for _, kcal in values)
                if daily_energy > 0:
                    paired += 1
                    energy += daily_energy
                    total += sum(n for n, _ in values) * factor
        result[key] = {"complete_days_with_both_values": paired,
                       "percent_of_recorded_energy": output(100 * total / energy) if paired else None}
    return result


def compare_reference(nutrient, summary, spec):
    if not isinstance(spec, dict) or spec.get("type") not in {"EAR", "AR", "RDA", "PRI", "AI", "UL", "CDRR", "guideline"}:
        raise ValueError("Specify the type of dietary reference value")
    if not spec.get("source") or not spec.get("group"):
        raise ValueError("Specify a source and the population group")
    reference = canonical_amount(nutrient, spec.get("value"), spec.get("unit"))
    if reference <= 0:
        raise ValueError("The reference value must be positive")
    actual = summary["mean_of_complete_day_totals"]
    return {"nutrient": nutrient, "unit": UNITS[nutrient], "reference_value": output(reference),
            "reference_type": spec["type"], "group": spec["group"], "source": spec["source"],
            "complete_days": summary["complete_days_with_values"], "observed_mean": actual,
            "percent_of_reference": output(100 * Decimal(str(actual)) / reference) if actual is not None else None}
