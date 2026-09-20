from __future__ import annotations

from itertools import combinations
import math
import pandas as pd

from .config import MEAL_LABELS
from .models import Bundle, Nutrients
from .scoring import bundle_objective
from .validation import validate_bundle

PROFILES = ("balance", "budget")


def row_nutrients(row: pd.Series) -> Nutrients:
    return Nutrients(
        float(row["kcal"]), float(row["protein_g"]), float(row["fat_g"]),
        float(row["carbs_g"]), float(row["fiber_g"]),
        float(row["sodium_mg"]), float(row["sugar_g"]),
    )


def rows_nutrients(rows: pd.DataFrame) -> Nutrients:
    total = Nutrients()
    for _, row in rows.iterrows():
        total = total + row_nutrients(row)
    return total


def parse_categories(rows: pd.DataFrame) -> set[str]:
    categories: set[str] = set()
    counted = rows[rows["counts_for_preference"].eq(1)]
    for value in counted["preference_categories"].astype(str):
        categories.update(part.strip() for part in value.split(";") if part.strip())
    return categories


def _billable_rows(rows: pd.DataFrame) -> pd.DataFrame:
    return rows[~rows["item_role"].eq("auto_free")]


def bundle_cost(rows: pd.DataFrame, service_mode: str, enforce_min_order: bool = True) -> tuple[float, float, float, float]:
    billable = _billable_rows(rows)
    item_subtotal = package_fee = delivery_fee = 0.0
    for _, shop_rows in billable.groupby("shop"):
        price_col = "price_dinein" if service_mode == "堂食" else "price_takeout"
        subtotal = float(shop_rows[price_col].sum())
        item_subtotal += subtotal
        if service_mode == "外卖":
            min_order = float(shop_rows["min_order"].max())
            if enforce_min_order and subtotal + 1e-9 < min_order:
                return math.inf, item_subtotal, package_fee, delivery_fee
            package_fee += float(shop_rows["package_fee_per_order"].max())
            delivery_fee += float(shop_rows["delivery_fee_per_order"].max())
    return item_subtotal + package_fee + delivery_fee, item_subtotal, package_fee, delivery_fee


def attach_free_soups(rows: pd.DataFrame, menu: pd.DataFrame, service_mode: str, meal: str) -> pd.DataFrame:
    if service_mode != "堂食" or meal == "breakfast":
        return rows
    base = rows[~rows["item_role"].eq("auto_free")]
    if base.empty:
        return rows
    selected_ids = set(rows["id"].astype(str))
    additions: list[pd.Series] = []
    for _, soup in menu[menu["item_role"].eq("auto_free")].iterrows():
        scope = str(soup["auto_attach_scope"])
        values = {part.strip() for part in str(soup["auto_attach_value"]).split(";") if part.strip()}
        shops = set(base["shop"].astype(str))
        locations = set(base["location"].astype(str))
        matched = False
        if scope == "location":
            matched = bool(values.intersection(locations))
        elif scope in {"shop", "shop_any"}:
            matched = bool(values.intersection(shops))
        if matched and soup["id"] not in selected_ids:
            additions.append(soup)
    if additions:
        rows = pd.concat([rows, pd.DataFrame(additions)], ignore_index=True)
    return rows.drop_duplicates("id")


def _movement_entities(rows: pd.DataFrame) -> tuple[tuple[str, ...], tuple[str, ...]]:
    counted = rows[(rows["movement_counted"].eq(1)) & (~rows["item_role"].eq("auto_free"))]
    return tuple(sorted(counted["shop"].unique())), tuple(sorted(counted["location"].unique()))


def make_bundle(
    rows: pd.DataFrame,
    menu: pd.DataFrame,
    meal: str,
    service_mode: str,
    preference: str,
    target: Nutrients,
    profile: str,
    desired_categories: set[str],
    light_mode: bool,
    target_budget: float | None,
    validate: bool = True,
) -> Bundle | None:
    rows = rows.drop_duplicates("id")
    base_rows = rows[~rows["item_role"].eq("auto_free")]
    if validate:
        ok, _ = validate_bundle(base_rows, menu, meal, service_mode)
        if not ok:
            return None

    rows = attach_free_soups(rows, menu, service_mode, meal)
    total_cost, item_subtotal, package_fee, delivery_fee = bundle_cost(rows, service_mode, enforce_min_order=validate)
    if not math.isfinite(total_cost):
        return None

    nutrients = rows_nutrients(rows)
    shops, locations = _movement_entities(rows)
    actual_categories = parse_categories(rows)
    has_light = bool(rows["is_light"].eq(1).any())
    has_soup_meal = bool(rows["soup_meal"].eq(1).any())
    soup_priority = int(rows["soup_priority"].max()) if not rows.empty else 0
    score = bundle_objective(
        nutrients, target, total_cost, len(shops), len(locations),
        service_mode, preference, profile, actual_categories,
        desired_categories, soup_priority, has_light, has_soup_meal,
        light_mode, target_budget,
    )
    has_soy_milk = bool(rows["name"].astype(str).str.contains("豆浆", na=False).any())
    if meal == "breakfast" and "饮品" in desired_categories:
        if has_soy_milk:
            score -= 2.4
        else:
            score += 1.2

    reasons: list[str] = []
    if len(shops) == 1:
        reasons.append("本餐在同一窗口/商家完成")
    elif len(shops) > 1:
        reasons.append(f"本餐涉及{len(shops)}家商家")
    if desired_categories:
        covered = desired_categories.intersection(actual_categories)
        if covered:
            reasons.append("覆盖偏好类别：" + "、".join(sorted(covered)))
    if meal == "breakfast" and has_soy_milk:
        reasons.append("早餐搭配豆浆")
    if has_soup_meal:
        reasons.append("包含粿条、米粉或汤粉类正餐")
    if light_mode and has_light:
        reasons.append("符合清淡标签")
    if rows["item_role"].eq("auto_free").any():
        reasons.append("堂食自动附带免费例汤，营养价值较低")
    if rows["is_fried"].sum() == 0:
        reasons.append("未包含油炸食品")
    if service_mode == "外卖":
        reasons.append(f"按{len(shops)}家店分别计算一次打包费和配送费")

    return Bundle(
        meal=meal,
        item_ids=tuple(rows["id"].astype(str)),
        item_names=tuple(rows["name"].astype(str)),
        shops=shops,
        locations=locations,
        nutrients=nutrients,
        item_subtotal=item_subtotal,
        package_fee=package_fee,
        delivery_fee=delivery_fee,
        total_cost=total_cost,
        local_score=score,
        preference_categories=tuple(sorted(actual_categories)),
        has_light_item=has_light,
        has_soup_meal=has_soup_meal,
        soup_priority=soup_priority,
        explanation=tuple(reasons),
    )


def _required_variants(seed: pd.Series, shop_rows: pd.DataFrame, light_mode: bool) -> list[pd.DataFrame]:
    base = pd.DataFrame([seed])
    provider = str(seed["provides_group"])
    if not provider:
        return [base]
    rule_rows = shop_rows[
        shop_rows["requires_group"].eq(provider)
        & shop_rows["choice_group"].astype(str).ne("")
        & shop_rows["choice_min"].gt(0)
    ]
    if rule_rows.empty:
        return [base]
    variants = [base]
    for _, options in rule_rows.groupby("choice_group"):
        if light_mode and options["is_light"].eq(1).any():
            options = options[options["is_light"].eq(1)]
        if len(options) > 2:
            options = options.assign(_choice_score=(
                -options["is_light"] * 0.8 - options["protein_g"] / 30
                - options["fiber_g"] / 10 + options["fat_g"] / 40
            )).nsmallest(2, "_choice_score")
        next_variants: list[pd.DataFrame] = []
        for variant in variants:
            for _, option in options.iterrows():
                next_variants.append(pd.concat([variant, pd.DataFrame([option])], ignore_index=True))
        variants = next_variants
    return variants


def _candidate_pool(current: pd.DataFrame, shop_rows: pd.DataFrame, light_mode: bool) -> pd.DataFrame:
    selected_ids = set(current["id"].astype(str))
    provides = {value for value in current["provides_group"].astype(str) if value}
    mask = shop_rows["standalone_allowed"].eq(1)
    if provides:
        mask = mask | shop_rows["requires_group"].isin(provides) | shop_rows["provides_group"].isin(provides)
    pool = shop_rows[mask & ~shop_rows["id"].astype(str).isin(selected_ids)].copy()
    pool = pool[~pool["item_role"].isin(["free_addon", "required_component", "auto_free"])]
    if light_mode:
        pool = pool[pool["is_light"].eq(1)]
    if len(pool) > 4:
        pool["_pool_score"] = (
            pool["price_dinein"] * 0.04 - pool["protein_g"] / 25
            - pool["fiber_g"] / 12 - pool["soup_priority"] * 0.4
            - pool["name"].astype(str).str.contains("豆浆", na=False).astype(int) * 1.5
            + pool["kcal"] / 3000
        )
        pool = pd.concat([
            pool.nsmallest(3, "_pool_score"), pool.nsmallest(1, "price_dinein")
        ]).drop_duplicates("id").head(4)
    return pool


def _greedy_expand(
    initial: pd.DataFrame,
    shop_rows: pd.DataFrame,
    menu: pd.DataFrame,
    meal: str,
    service_mode: str,
    preference: str,
    target: Nutrients,
    profile: str,
    desired_categories: set[str],
    light_mode: bool,
    target_budget: float | None,
    max_items: int,
) -> list[Bundle]:
    current = initial.drop_duplicates("id").copy()
    results: list[Bundle] = []
    for _ in range(max_items):
        valid = make_bundle(
            current, menu, meal, service_mode, preference, target, profile,
            desired_categories, light_mode, target_budget, validate=True,
        )
        if valid:
            results.append(valid)
        pool = _candidate_pool(current, shop_rows, light_mode)
        if pool.empty or len(current) >= max_items:
            break

        current_bundle = make_bundle(
            current, menu, meal, service_mode, preference, target, profile,
            desired_categories, light_mode, target_budget, validate=False,
        )
        current_score = current_bundle.local_score if current_bundle else math.inf
        best_row = None
        best_score = math.inf
        for _, row in pool.iterrows():
            trial = pd.concat([current, pd.DataFrame([row])], ignore_index=True).drop_duplicates("id")
            trial_bundle = make_bundle(
                trial, menu, meal, service_mode, preference, target, profile,
                desired_categories, light_mode, target_budget, validate=False,
            )
            if trial_bundle and trial_bundle.local_score < best_score:
                best_score = trial_bundle.local_score
                best_row = row
        if best_row is None:
            break
        min_order_unmet = not math.isfinite(bundle_cost(current, service_mode, enforce_min_order=True)[0])
        too_light = rows_nutrients(current).kcal < target.kcal * 0.55
        missing_categories = bool(desired_categories - parse_categories(current))
        if not (min_order_unmet or too_light or missing_categories) and best_score >= current_score - 0.03:
            break
        current = pd.concat([current, pd.DataFrame([best_row])], ignore_index=True)

    final = make_bundle(
        current, menu, meal, service_mode, preference, target, profile,
        desired_categories, light_mode, target_budget, validate=True,
    )
    if final:
        results.append(final)
    return results


def _custom_mix_bundles(
    shop_rows: pd.DataFrame,
    menu: pd.DataFrame,
    meal: str,
    service_mode: str,
    preference: str,
    target: Nutrients,
    desired_categories: set[str],
    light_mode: bool,
    target_budget: float | None,
) -> list[Bundle]:
    results: list[Bundle] = []
    pool_rows = shop_rows[shop_rows["is_light"].eq(1)] if light_mode else shop_rows
    staples = pool_rows[pool_rows["component_type"].eq("staple")]
    if staples.empty:
        return results
    staples = staples.sort_values(["price_dinein", "kcal"]).head(2)
    for _, seed in staples.iterrows():
        for profile in PROFILES:
            current = pd.DataFrame([seed])
            for _ in range(4):
                valid = make_bundle(
                    current, menu, meal, service_mode, preference, target, profile,
                    desired_categories, light_mode, target_budget, validate=True,
                )
                if valid:
                    results.append(valid)
                candidate_pool = pool_rows[~pool_rows["id"].isin(current["id"])].copy().head(12)
                if candidate_pool.empty or len(current) >= 6:
                    break
                best_row = None
                best_score = math.inf
                for _, row in candidate_pool.iterrows():
                    trial = pd.concat([current, pd.DataFrame([row])], ignore_index=True)
                    bundle = make_bundle(
                        trial, menu, meal, service_mode, preference, target, profile,
                        desired_categories, light_mode, target_budget, validate=False,
                    )
                    if bundle and bundle.local_score < best_score:
                        best_score = bundle.local_score
                        best_row = row
                if best_row is None:
                    break
                current = pd.concat([current, pd.DataFrame([best_row])], ignore_index=True)
    return results


def generate_candidates(
    menu: pd.DataFrame,
    meal: str,
    target: Nutrients,
    service_mode: str,
    preference: str,
    avoid_fried: bool = False,
    desired_categories: set[str] | None = None,
    light_mode: bool = False,
    target_budget: float | None = None,
    max_candidates: int = 40,
    progress_callback=None,
) -> tuple[list[Bundle], list[dict]]:
    desired_categories = set(desired_categories or set())
    availability = {"breakfast": "available_breakfast", "lunch": "available_lunch", "dinner": "available_dinner"}[meal]
    service_column = "dinein_available" if service_mode == "堂食" else "takeout_available"
    breakfast_soy = (
        (meal == "breakfast")
        & menu["name"].astype(str).str.contains("豆浆", na=False)
        & menu["standalone_allowed"].eq(1)
    )
    eligible = menu[
        menu[availability].eq(1)
        & menu[service_column].eq(1)
        & ~menu["item_role"].eq("auto_free")
        & (menu["is_drink"].eq(0) | breakfast_soy)
    ].copy()
    if avoid_fried:
        eligible = eligible[eligible["is_fried"].eq(0)]

    available_categories: set[str] = set()
    for value in eligible["preference_categories"].astype(str):
        available_categories.update(x for x in value.split(";") if x)
    effective_desired = desired_categories.intersection(available_categories)

    shop_stats = []
    for shop, group in eligible.groupby("shop"):
        category_hits = group["preference_categories"].apply(
            lambda value: len(effective_desired.intersection({x for x in str(value).split(";") if x}))
        ).max()
        budget_relevance = 0.0
        if target_budget and target_budget > 0:
            min_gap = float((group["price_dinein"] - target_budget).abs().min())
            budget_relevance = max(0.0, 2.5 - min_gap / target_budget * 2.5)
        relevance = (
            float(category_hits) * 2.0 + float(group["soup_priority"].max()) * (2.5 if "汤" in effective_desired else 0.4)
            + float(group["light_anchor"].max()) * (2.5 if light_mode else 0.0)
            + budget_relevance
            - float(group["price_dinein"].min()) * 0.02
        )
        shop_stats.append((relevance, shop))
    shop_limit = 5 if light_mode or "汤" in effective_desired else 7
    selected_shops = {shop for _, shop in sorted(shop_stats, reverse=True)[:shop_limit]}
    eligible = eligible[eligible["shop"].isin(selected_shops)]

    if progress_callback:
        progress_callback(
            f"🔍 {MEAL_LABELS[meal]}：从 {len(eligible['shop'].unique())} 家商家中"
            f"筛选出 {len(selected_shops)} 家相关商家，开始生成候选套餐……"
        )

    all_bundles: list[Bundle] = []
    trace: list[dict] = []
    for shop, shop_rows in eligible.groupby("shop"):
        shop_results: list[Bundle] = []
        if shop_rows["shop_mode"].eq("custom_mix").all():
            shop_results.extend(_custom_mix_bundles(
                shop_rows, menu, meal, service_mode, preference, target,
                effective_desired, light_mode, target_budget,
            ))
        else:
            seeds = shop_rows[shop_rows["meal_anchor"].eq(1)].copy()
            if light_mode:
                seeds = seeds[seeds["light_anchor"].eq(1)]
            if seeds.empty:
                continue
            seeds["_desired_hits"] = seeds["preference_categories"].apply(
                lambda value: len(effective_desired.intersection({x for x in str(value).split(";") if x}))
            )
            seeds["_seed_score"] = (
                seeds["price_dinein"] * 0.04
                - seeds["protein_g"] / 22 - seeds["fiber_g"] / 10
                - seeds["soup_priority"] * (0.9 if "汤" in effective_desired or light_mode else 0.2)
                - seeds["_desired_hits"] * 0.6
                + (seeds["kcal"] - target.kcal).abs() / max(target.kcal, 1)
            )
            seed_sets = [seeds.nsmallest(3, "_seed_score"), seeds.nsmallest(1, "price_dinein")]
            if target_budget and target_budget > 0:
                seed_sets.append(seeds.assign(_budget_gap=(seeds["price_dinein"] - target_budget).abs()).nsmallest(2, "_budget_gap"))
            if "汤" in effective_desired or light_mode:
                seed_sets.append(seeds.nlargest(2, "soup_priority"))
            seeds = pd.concat(seed_sets).drop_duplicates("id").head(6)

            for _, seed in seeds.iterrows():
                for initial in _required_variants(seed, shop_rows, light_mode):
                    for profile in PROFILES:
                        shop_results.extend(_greedy_expand(
                            initial, shop_rows, menu, meal, service_mode, preference,
                            target, profile, effective_desired, light_mode,
                            target_budget, 4 if meal == "breakfast" else 3,
                        ))

        dedup: dict[tuple[str, ...], Bundle] = {}
        for bundle in shop_results:
            key = tuple(sorted(bundle.item_ids))
            if key not in dedup or bundle.local_score < dedup[key].local_score:
                dedup[key] = bundle
        ranked = sorted(dedup.values(), key=lambda bundle: bundle.local_score)[:8]
        all_bundles.extend(ranked)
        trace.append({"meal": meal, "shop": shop, "legal_single_shop_candidates": len(ranked)})
        if progress_callback:
            progress_callback(f"   └ {shop}：生成 {len(ranked)} 个合法候选")

    dedup_all: dict[tuple[str, ...], Bundle] = {}
    for bundle in all_bundles:
        key = tuple(sorted(bundle.item_ids))
        if key not in dedup_all or bundle.local_score < dedup_all[key].local_score:
            dedup_all[key] = bundle
    single = sorted(dedup_all.values(), key=lambda bundle: bundle.local_score)

    pair_candidates: list[Bundle] = []
    indexed = menu.set_index("id", drop=False)
    for left, right in combinations(single[:5], 2):
        if set(left.shops) & set(right.shops):
            continue
        if left.nutrients.kcal + right.nutrients.kcal > target.kcal * 1.45 + 150:
            continue
        ids = [item_id for item_id in left.item_ids + right.item_ids if not item_id.startswith("F")]
        rows = indexed.loc[ids]
        if isinstance(rows, pd.Series):
            rows = rows.to_frame().T
        bundle = make_bundle(
            rows.reset_index(drop=True), menu, meal, service_mode, preference,
            target, "balance", effective_desired, light_mode, target_budget, validate=True,
        )
        if bundle:
            pair_candidates.append(bundle)

    if progress_callback and pair_candidates:
        progress_callback(f"   └ 跨商家组合：生成 {len(pair_candidates)} 个两店搭配候选")

    final_dedup: dict[tuple[str, ...], Bundle] = {}
    for bundle in single + pair_candidates:
        key = tuple(sorted(bundle.item_ids))
        if key not in final_dedup or bundle.local_score < final_dedup[key].local_score:
            final_dedup[key] = bundle
    final = sorted(final_dedup.values(), key=lambda bundle: bundle.local_score)[:max_candidates]
    if progress_callback:
        progress_callback(f"✅ {MEAL_LABELS[meal]}候选生成完成：共计 {len(final)} 个候选套餐")
    return final, trace
