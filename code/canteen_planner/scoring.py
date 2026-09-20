from __future__ import annotations
from .models import Nutrients


def nutrient_penalty(n: Nutrients, target: Nutrients, profile: str = "balance") -> float:
    protein_weight = 3.8 if profile == "protein" else 3.0
    fiber_weight = 2.5 if profile == "fiber" else 1.7
    return (
        max(target.kcal - n.kcal, 0) / max(target.kcal, 1) * 3.0
        + max(n.kcal - target.kcal, 0) / max(target.kcal, 1) * 2.2
        + max(target.protein_g - n.protein_g, 0) / max(target.protein_g, 1) * protein_weight
        + max(n.protein_g - target.protein_g, 0) / max(target.protein_g, 1) * 0.4
        + abs(n.carbs_g - target.carbs_g) / max(target.carbs_g, 1) * 0.8
        + max(n.fat_g - target.fat_g, 0) / max(target.fat_g, 1) * 2.2
        + max(target.fiber_g - n.fiber_g, 0) / max(target.fiber_g, 1) * fiber_weight
        + max(n.sodium_mg - target.sodium_mg, 0) / max(target.sodium_mg, 1) * 2.0
        + max(n.sugar_g - target.sugar_g, 0) / max(target.sugar_g, 1) * 2.0
    )


def budget_penalty(cost: float, target_budget: float | None) -> float:
    if target_budget is None or target_budget <= 0:
        return cost * 0.055
    if cost <= target_budget:
        return (target_budget - cost) / target_budget * 2.5
    return 10.0 + (cost - target_budget) / target_budget * 20.0


def category_penalty(actual: set[str], desired: set[str], soup_priority: int) -> float:
    if not desired:
        return 0.0
    missing = desired - actual
    score = len(missing) * 1.35
    if "汤" in desired:
        if soup_priority >= 3:
            score -= 1.8
        elif soup_priority == 2:
            score -= 1.0
        elif "汤" in actual:
            score -= 0.3
        else:
            score += 1.0
    if not missing:
        score -= 0.45
    return score


def bundle_objective(
    n: Nutrients,
    target: Nutrients,
    cost: float,
    vendor_count: int,
    location_count: int,
    service_mode: str,
    preference: str,
    profile: str,
    actual_categories: set[str],
    desired_categories: set[str],
    soup_priority: int,
    has_light_item: bool,
    has_soup_meal: bool,
    light_mode: bool,
    target_budget: float | None,
) -> float:
    score = nutrient_penalty(n, target, profile)
    score += category_penalty(actual_categories, desired_categories, soup_priority)
    score += budget_penalty(cost, target_budget) * (1.8 if profile == "budget" else 1.0)

    if service_mode == "外卖":
        score += max(vendor_count - 1, 0) * 2.5
    elif preference == "便利型":
        score += max(vendor_count - 1, 0) * 8.0 + max(location_count - 1, 0) * 4.0
    else:
        score += max(vendor_count - 1, 0) * 0.25

    if light_mode:
        if not has_light_item:
            score += 12.0
        if has_soup_meal:
            score -= 1.2
    return score
