"""Nutri-Score 2023 food profiling rules published by Santé publique France."""
from bisect import bisect_left, bisect_right
from decimal import Decimal

METHOD = "nutri_score_2023"
SPEC = "https://www.santepubliquefrance.fr/sites/default/files/rdd/document/FAQ-updatedAlgo-V11.pdf"
CATEGORIES = ("general", "cheese", "red_meat", "fats_oils_nuts_seeds", "beverage", "water")
FOOD_SUGAR = (3.4, 6.8, 10, 14, 17, 20, 24, 27, 31, 34, 37, 41, 44, 48, 51)
DRINK_SUGAR = (0.5, 2, 3.5, 5, 6, 7, 8, 9, 10, 11)
DRINK_ENERGY = (30, 90, 150, 210, 240, 270, 300, 330, 360, 390)
FOOD_PROTEIN = (2.4, 4.8, 7.2, 9.6, 12, 14, 17)
DRINK_PROTEIN = (1.2, 1.5, 1.8, 2.1, 2.4, 2.7, 3)
FIBER = (3, 4.1, 5.2, 6.3, 7.4)
SALT = tuple(Decimal(i) / 5 for i in range(1, 21))
KEYS = ("energy_kj", "total_sugars_g", "saturated_fat_g", "salt_g", "sodium_mg",
        "protein_g", "fiber_g", "fat_g", "fruit_vegetable_legume_percent", "non_nutritive_sweeteners")
CARD_UNITS = {key: "g" for key in ("total_sugars_g", "saturated_fat_g", "salt_g", "protein_g", "fiber_g", "fat_g")}
CARD_UNITS.update(energy_kj="kJ", sodium_mg="mg")


def number(value, key):
    if type(value) not in (int, float, Decimal):
        raise ValueError(f"{key} must be a finite nonnegative number")
    value = Decimal(str(value))
    if not value.is_finite() or value < 0:
        raise ValueError(f"{key} must be a finite nonnegative number")
    return value


def points(value, cutoffs, *, at_threshold=False):
    """Published tables award points above a cutoff, except the fat ratio."""
    bounds = tuple(Decimal(str(item)) for item in cutoffs)
    return (bisect_right if at_threshold else bisect_left)(bounds, value)


def score(category, basis, values):
    """Score one composition. Pass an explicit category and label-basis inputs."""
    if category not in CATEGORIES:
        raise ValueError("Select a supported Nutri-Score category")
    if basis not in ("100g", "100ml") or (category in ("water", "beverage") and basis != "100ml"):
        raise ValueError("Use the declared 100g or 100ml basis, with 100ml for beverages")
    if not isinstance(values, dict) or values.keys() - set(KEYS):
        raise ValueError("Supply only recognized Nutri-Score inputs")
    result = {"method": METHOD, "specification": SPEC, "category": category, "basis": basis}
    if category == "water":
        if values:
            raise ValueError("Use the water category only for qualifying water, with empty inputs")
        return {**result, "status": "calculated", "grade": "A", "score": None}

    drink = category == "beverage"
    fats = category == "fats_oils_nuts_seeds"
    required = {"total_sugars_g", "saturated_fat_g", "protein_g", "fiber_g",
                "fruit_vegetable_legume_percent", "fat_g" if fats else "energy_kj"}
    if drink:
        required.add("non_nutritive_sweeteners")
    known = {key: number(value, key) for key, value in values.items()
             if value is not None and key != "non_nutritive_sweeteners"}
    sweeteners = values.get("non_nutritive_sweeteners")
    if sweeteners is not None and not isinstance(sweeteners, bool):
        raise ValueError("non_nutritive_sweeteners must be true or false")
    missing = required - known.keys()
    if sweeteners is not None:
        missing.discard("non_nutritive_sweeteners")
    if not ({"salt_g", "sodium_mg"} & known.keys()):
        missing.add("salt_g")
    if missing:
        return {**result, "status": "insufficient_data", "grade": None, "score": None, "missing": sorted(missing)}

    fruit = known["fruit_vegetable_legume_percent"]
    if fruit > 100:
        raise ValueError("fruit_vegetable_legume_percent must be between 0 and 100")
    saturates = known["saturated_fat_g"]
    salt = known["salt_g"] if "salt_g" in known else known["sodium_mg"] * Decimal("0.0025")
    unfavorable = {
        "sugars": points(known["total_sugars_g"], DRINK_SUGAR if drink else FOOD_SUGAR),
        "salt": points(salt, SALT),
    }
    if fats:
        fat = known["fat_g"]
        if not fat or saturates > fat:
            raise ValueError("Fat must be positive and at least as high as saturated fat")
        unfavorable["energy_from_saturates"] = points(saturates * 37, range(120, 1201, 120))
        unfavorable["saturated_fat_ratio"] = points(saturates * 100 / fat, range(10, 65, 6), at_threshold=True)
    else:
        unfavorable["energy"] = points(known["energy_kj"], DRINK_ENERGY if drink else range(335, 3351, 335))
        unfavorable["saturated_fat"] = points(saturates, range(1, 11))
    if drink:
        unfavorable["non_nutritive_sweeteners"] = 4 if sweeteners else 0

    group = points(fruit, (40, 60, 80))
    protein = points(known["protein_g"], DRINK_PROTEIN if drink else FOOD_PROTEIN)
    if category == "red_meat":
        protein = min(protein, 2)
    total_unfavorable = sum(unfavorable.values())
    count_protein = drink or category == "cheese" or total_unfavorable < (7 if fats else 11)
    favorable = {
        "protein": protein if count_protein else 0,
        "fiber": points(known["fiber_g"], FIBER),
        "fruits_vegetables_legumes": group * 2 if drink else (0, 1, 2, 5)[group],
    }
    total = total_unfavorable - sum(favorable.values())
    if drink:
        grade = "BCDE"[bisect_left((2, 6, 9), total)]
    else:
        grade = "ABCDE"[bisect_left((-6 if fats else 0, 2, 10, 18), total)]
    return {**result, "status": "calculated", "score": total, "grade": grade,
            "unfavorable_points": unfavorable, "favorable_points": favorable,
            "protein_points_counted": count_protein, "inputs": {**values, "salt_g": float(salt)}}


def score_card(card, assessment, provenance):
    """Select same-basis fields, keeping composition and evidence separate."""
    if not isinstance(assessment, dict) or assessment.keys() - {
        "category", "basis", "fruit_vegetable_legume_percent", "non_nutritive_sweeteners", "energy_kj",
    }:
        raise ValueError("Supply explicit category, basis and any additional scoring inputs")
    if not isinstance(provenance, str) or not provenance.strip():
        raise ValueError("Cite the label, recipe or other source for the scoring inputs and category")
    category, basis = assessment.get("category"), assessment.get("basis")
    evidence = {}
    values = {}
    if category == "water":
        if assessment.keys() != {"category", "basis"}:
            raise ValueError("Water classification takes only category and basis")
    else:
        for key, item in card["nutrients"].items():
            if (key in CARD_UNITS and item.get("basis") == basis and item.get("source")
                    and not item.get("method", "").startswith(("estimated_", "personal_", "stored_card"))):
                if item.get("unit") != CARD_UNITS[key]:
                    raise ValueError(f"{key} requires {CARD_UNITS[key]} for scoring")
                values[key] = item["value"]
                evidence[key] = item["source"]
        for key in ("energy_kj", "fruit_vegetable_legume_percent", "non_nutritive_sweeteners"):
            if key in assessment:
                values[key] = assessment[key]
                evidence[key] = provenance
    return {**score(category, basis, values), "food_id": card["id"],
            "assessment_source": provenance, "input_sources": evidence}


def evaluate(request, catalog):
    """Dispatch normalized input or a catalog card with separately sourced metadata."""
    if not isinstance(request, dict):
        raise ValueError("Use a JSON object")
    if request.keys() == {"category", "basis", "values"}:
        return score(request["category"], request["basis"], request["values"])
    if request.keys() == {"food_id", "assessment", "source"}:
        if not isinstance(request["food_id"], str) or request["food_id"] not in catalog:
            raise ValueError("Unknown food ID")
        return score_card(catalog[request["food_id"]], request["assessment"], request["source"])
    raise ValueError("Supply category, basis and values, or food_id, assessment and source")
