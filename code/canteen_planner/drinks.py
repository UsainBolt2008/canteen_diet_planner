from __future__ import annotations
import math
import pandas as pd
from .meal_candidates import rows_nutrients, bundle_cost
from .models import Bundle, Nutrients


BREAKFAST_ONLY_SHOPS = {"面夫子", "营养早餐"}
FREE_SOUP_WORDS = "免费例汤|免费汤|例汤|营养汤"
PREMIUM_SHOPS = {"茶百道", "挪瓦咖啡", "肯德基"}


def _service_filter(menu: pd.DataFrame, service_mode: str) -> pd.Series:
    if service_mode == "堂食":
        return menu["dinein_available"].eq(1)
    return menu["takeout_available"].eq(1)


def _is_breakfast_only(rows: pd.DataFrame) -> pd.Series:
    return rows["available_breakfast"].eq(1) & rows["available_lunch"].eq(0) & rows["available_dinner"].eq(0)


def _drink_rows(menu: pd.DataFrame, service_mode: str, consumed_meals: list[str] | None = None) -> pd.DataFrame:
    consumed_meals = consumed_meals or []
    name = menu["name"].astype(str)
    shop = menu["shop"].astype(str)
    drink_like = (
        menu["is_drink"].eq(1)
        | menu["category"].astype(str).eq("饮品")
        | name.str.contains("冰淇淋|甜筒|圣代|奶昔|咖啡|奶茶|柠檬水|果茶|乌龙|红茶|绿茶|可乐|雪碧|冰饮|茶", regex=True, na=False)
    )
    rows = menu[
        drink_like
        & _service_filter(menu, service_mode)
        & menu["standalone_allowed"].eq(1)
        & ~menu["item_role"].isin(["addon", "free_addon", "required_component", "auto_free"])
        & ~name.str.contains(FREE_SOUP_WORDS, regex=True, na=False)
        & ~menu["counts_for_preference"].eq(0)
        & ~_is_breakfast_only(menu)
    ].copy()
    if "breakfast" in consumed_meals:
        rows = rows[~shop.isin(BREAKFAST_ONLY_SHOPS)]
    return rows.drop_duplicates("id")


def _drink_cap(budget_left: float | None, planned_cost: float = 0.0, full_budget: float | None = None) -> float | None:
    if full_budget is not None and full_budget > 0 and budget_left is not None and budget_left <= 0:
        return 0.0
    if budget_left is None:
        return 10.0
    if budget_left <= 0:
        return 0.0
    if planned_cost <= 0:
        return min(budget_left, 8.0)
    base_cap = 6.0 if planned_cost < 15 else 8.0
    ratio_cap = planned_cost * 0.42
    cap = min(budget_left, max(base_cap, ratio_cap))
    if full_budget and full_budget >= 60 and planned_cost >= 25:
        cap = min(budget_left, 16.0)
    else:
        cap = min(cap, 12.0)
    return max(2.5, cap)


def _merchant_rank(shop: str, cap: float | None) -> float:
    if "蜜雪冰城" in shop:
        return -8.0
    if "茶百道" in shop:
        return -1.0 if cap is not None and cap >= 12 else 3.0
    if "挪瓦咖啡" in shop:
        return -0.4 if cap is not None and cap >= 14 else 4.2
    if "肯德基" in shop:
        return 0.2 if cap is not None and cap >= 15 else 5.0
    return 0.0


def _score(row: pd.Series, bundle: Bundle, target: Nutrients, current: Nutrients, cap: float | None, budget_left: float | None) -> float:
    after = current + bundle.nutrients
    remaining_energy = max(target.kcal - current.kcal, 0)
    remaining_sugar = max(target.sugar_g - current.sugar_g, 0)
    price = bundle.total_cost
    shop = str(row["shop"])
    name = str(row["name"])
    score = 0.0
    score += price * 0.9
    score += max(price - 8.0, 0) * 2.3
    score += max(price - 12.0, 0) * 4.0
    if cap is not None and price > cap:
        score += 80.0 + (price - cap) * 8.0
    if budget_left is not None and price > budget_left:
        score += 120.0 + (price - budget_left) * 10.0
    score += bundle.nutrients.sugar_g / max(remaining_sugar, 12.0) * 5.5
    score += max(after.sugar_g - target.sugar_g, 0) / max(target.sugar_g, 1) * 35.0
    score += bundle.nutrients.kcal / max(remaining_energy, 180.0) * 2.1
    score += max(after.kcal - target.kcal, 0) / max(target.kcal, 1) * 25.0
    score += bundle.nutrients.fat_g / max(target.fat_g, 1) * 6.0
    score += _merchant_rank(shop, cap)
    if price <= 4.0:
        score -= 3.2
    elif price <= 6.0:
        score -= 2.2
    elif price <= 8.0:
        score -= 1.1
    if bundle.nutrients.sugar_g <= 8.0:
        score -= 2.0
    elif bundle.nutrients.sugar_g <= 18.0:
        score -= 0.8
    elif bundle.nutrients.sugar_g >= 55.0:
        score += 2.5
    if "美式" in name or "无糖" in name:
        score -= 1.5
    if "冰淇淋" in name or "甜筒" in name or "圣代" in name or "奶昔" in name:
        score += 1.3
    return score


def _make_bundle(row: pd.Series, service_mode: str, target: Nutrients, current: Nutrients, cap: float | None, budget_left: float | None) -> Bundle | None:
    rows = pd.DataFrame([row])
    total_cost, item_subtotal, package_fee, delivery_fee = bundle_cost(rows, service_mode, enforce_min_order=True)
    if not math.isfinite(total_cost):
        return None
    nutrients = rows_nutrients(rows)
    raw_bundle = Bundle(
        meal="drink",
        item_ids=(str(row["id"]),),
        item_names=(str(row["name"]),),
        shops=(str(row["shop"]),),
        locations=(str(row["location"]),),
        nutrients=nutrients,
        item_subtotal=item_subtotal,
        package_fee=package_fee,
        delivery_fee=delivery_fee,
        total_cost=total_cost,
        local_score=0.0,
        preference_categories=("饮品",),
        has_light_item=False,
        has_soup_meal=False,
        soup_priority=0,
        explanation=(),
    )
    score = _score(row, raw_bundle, target, current, cap, budget_left)
    reasons = []
    if "蜜雪冰城" in str(row["shop"]):
        reasons.append("优先考虑蜜雪冰城等低价饮品")
    elif str(row["shop"]) in PREMIUM_SHOPS:
        reasons.append("价格较高，仅在预算充足时作为备选")
    if total_cost <= 6.0:
        reasons.append("价格较低")
    elif total_cost <= 10.0:
        reasons.append("价格适中")
    else:
        reasons.append("价格偏高")
    if nutrients.sugar_g > max(target.sugar_g - current.sugar_g, 0):
        reasons.append("糖分较高，建议少量选择")
    else:
        reasons.append("糖分仍在可控范围内")
    if service_mode == "外卖":
        reasons.append("已计入该店一次打包费和配送费")
    return Bundle(
        meal="drink",
        item_ids=raw_bundle.item_ids,
        item_names=raw_bundle.item_names,
        shops=raw_bundle.shops,
        locations=raw_bundle.locations,
        nutrients=raw_bundle.nutrients,
        item_subtotal=raw_bundle.item_subtotal,
        package_fee=raw_bundle.package_fee,
        delivery_fee=raw_bundle.delivery_fee,
        total_cost=raw_bundle.total_cost,
        local_score=score,
        preference_categories=raw_bundle.preference_categories,
        has_light_item=False,
        has_soup_meal=False,
        soup_priority=0,
        explanation=tuple(reasons),
    )


def recommend_drinks(
    menu: pd.DataFrame,
    target: Nutrients,
    current: Nutrients,
    service_mode: str,
    budget_left: float | None,
    count: int = 3,
    remaining_meals: list[str] | None = None,
    consumed_meals: list[str] | None = None,
    planned_cost: float = 0.0,
    full_budget: float | None = None,
) -> tuple[list[Bundle], list[str]]:
    count = max(1, min(6, int(count)))
    cap = _drink_cap(budget_left, planned_cost, full_budget)
    rows = _drink_rows(menu, service_mode, consumed_meals)
    bundles: list[Bundle] = []
    for _, row in rows.iterrows():
        bundle = _make_bundle(row, service_mode, target, current, cap, budget_left)
        if bundle is not None:
            bundles.append(bundle)
    if not bundles:
        return [], ["没有找到可单独购买的额外饮品或冰淇淋。"]
    under_cap = [bundle for bundle in bundles if cap is None or bundle.total_cost <= cap + 1e-9]
    if full_budget is not None and full_budget > 0 and budget_left is not None:
        under_cap = [bundle for bundle in under_cap if bundle.total_cost <= budget_left + 1e-9]
    def _bundle_tier(bundle: Bundle) -> tuple[int, float]:
        shop_text = "".join(bundle.shops)
        if "蜜雪冰城" in shop_text:
            tier = 0
        elif any(name in shop_text for name in PREMIUM_SHOPS):
            tier = 2 if cap is not None and cap >= 12 else 3
        else:
            tier = 1
        return tier, bundle.local_score

    if not under_cap and full_budget is not None and full_budget > 0 and budget_left is not None and budget_left > 0:
        return [], [f"当前剩余预算约¥{budget_left:.2f}，不足以选择合适的额外饮品。"]
    ranked = sorted(under_cap or bundles, key=_bundle_tier)
    selected: list[Bundle] = []
    used_ids: set[tuple[str, ...]] = set()
    for bundle in ranked:
        key = tuple(sorted(bundle.item_ids))
        if key in used_ids:
            continue
        selected.append(bundle)
        used_ids.add(key)
        if len(selected) >= count:
            break
    warnings = []
    if cap is not None and cap > 0:
        warnings.append(f"额外饮品建议价格已控制在约¥{cap:.2f}以内，避免饮品占用过多正餐预算。")
    elif full_budget is not None and full_budget > 0:
        warnings.append("当前预算已基本用于正餐，饮品仅显示最低代价备选。")
    if current.sugar_g >= target.sugar_g:
        warnings.append("今日糖分估算已偏高，饮品建议优先选择低糖或无糖。")
    if not any("蜜雪冰城" in "".join(bundle.shops) for bundle in selected) and any("蜜雪冰城" in str(shop) for shop in rows["shop"].astype(str)):
        warnings.append("蜜雪冰城存在可选饮品，但当前预算或糖分限制使其未排在最前。")
    return selected[:count], warnings
