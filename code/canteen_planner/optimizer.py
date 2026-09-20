from __future__ import annotations
from dataclasses import dataclass
import math
import pandas as pd

from .config import DP_BINS, MEAL_LABELS
from .meal_candidates import generate_candidates
from .models import Bundle, Nutrients, PlanResult
from .nutrition import split_budget, split_remaining_target
from .scoring import nutrient_penalty, budget_penalty


@dataclass
class _State:
    bundles: tuple[Bundle, ...]
    nutrients: Nutrients
    cost: float
    local_score_sum: float
    used_item_ids: frozenset[str]
    repeat_count: int
    has_light_soup: bool


def _bin(n: Nutrients, has_light_soup: bool) -> tuple[int, ...]:
    return (
        round(n.kcal / DP_BINS["kcal"]),
        round(n.protein_g / DP_BINS["protein_g"]),
        round(n.fat_g / DP_BINS["fat_g"]),
        round(n.carbs_g / DP_BINS["carbs_g"]),
        round(n.fiber_g / DP_BINS["fiber_g"]),
        int(has_light_soup),
    )


def nutrients_from_selected(menu: pd.DataFrame, selections: dict[str, float]) -> Nutrients:
    if not selections:
        return Nutrients()
    indexed = menu.set_index("id", drop=False)
    total = Nutrients()
    for item_id, servings in selections.items():
        if item_id not in indexed.index:
            continue
        row = indexed.loc[item_id]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        total = total + Nutrients(
            float(row["kcal"]) * servings, float(row["protein_g"]) * servings,
            float(row["fat_g"]) * servings, float(row["carbs_g"]) * servings,
            float(row["fiber_g"]) * servings, float(row["sodium_mg"]) * servings,
            float(row["sugar_g"]) * servings,
        )
    return total


def _select_diverse_options(primary: Bundle, candidates: list[Bundle], count: int) -> list[Bundle]:
    selected = [primary]
    remaining = [bundle for bundle in candidates if set(bundle.item_ids) != set(primary.item_ids)]
    while remaining and len(selected) < count:
        best = min(
            remaining,
            key=lambda bundle: bundle.local_score
            + max(
                (len(set(bundle.item_ids).intersection(option.item_ids)) / max(len(bundle.item_ids), 1))
                for option in selected
            ) * 1.2
            + sum(set(bundle.shops) == set(option.shops) for option in selected) * 0.12,
        )
        selected.append(best)
        remaining.remove(best)
    return selected


def optimize_plan(
    menu: pd.DataFrame,
    daily_target: Nutrients,
    consumed: Nutrients,
    remaining_meals: list[str],
    service_mode: str,
    preference: str,
    budget: float | None = None,
    avoid_fried: bool = False,
    desired_categories: set[str] | None = None,
    light_mode: bool = False,
    recommendation_count: int = 3,
    beam_width: int = 300,
    progress_callback=None,
) -> PlanResult:
    if not remaining_meals:
        raise ValueError("没有需要规划的餐次。")
    if not 1 <= recommendation_count <= 6:
        raise ValueError("每餐推荐数量必须在1到6之间。")
    if service_mode == "外卖":
        preference = "经济型"

    desired_categories = set(desired_categories or set())
    remaining = (daily_target - consumed).clip_min()
    meal_targets = split_remaining_target(remaining, remaining_meals)
    meal_budgets = split_budget(budget, remaining_meals)

    candidates: dict[str, list[Bundle]] = {}
    greedy_trace: list[dict] = []
    for meal in remaining_meals:
        if progress_callback:
            progress_callback(f"🍽️ 正在为{MEAL_LABELS[meal]}生成候选套餐……")
        meal_candidates, trace = generate_candidates(
            menu=menu,
            meal=meal,
            target=meal_targets[meal],
            service_mode=service_mode,
            preference=preference,
            avoid_fried=avoid_fried,
            desired_categories=desired_categories,
            light_mode=light_mode,
            target_budget=meal_budgets[meal],
            progress_callback=progress_callback,
        )
        if not meal_candidates:
            raise ValueError(f"{meal}没有合法候选，请检查营业餐次、清淡筛选或商品依赖标签。")
        candidates[meal] = meal_candidates
        greedy_trace.extend(trace)

    regular_remaining = any(meal in {"lunch", "dinner"} for meal in remaining_meals)
    warnings: list[str] = []

    def run_dp(enforce_budget: bool) -> list[_State]:
        states: dict[tuple[int, ...], _State] = {
            (0, 0, 0, 0, 0, 0): _State((), Nutrients(), 0.0, 0.0, frozenset(), 0, False)
        }
        processed_target = Nutrients()
        dp_trace.clear()
        budget_label = "（强制预算约束）" if enforce_budget else "（放宽预算）"
        for meal in remaining_meals:
            processed_target = processed_target + meal_targets[meal]
            next_states: dict[tuple[int, ...], _State] = {}
            transitions = 0
            for state in states.values():
                for bundle in candidates[meal]:
                    transitions += 1
                    cost = state.cost + bundle.total_cost
                    if enforce_budget and budget and budget > 0 and cost > budget + 1e-9:
                        continue
                    n = state.nutrients + bundle.nutrients
                    paid_ids = {item_id for item_id in bundle.item_ids if not item_id.startswith("F")}
                    overlap = len(state.used_item_ids.intersection(paid_ids))
                    repeat_count = state.repeat_count + overlap
                    has_light_soup = state.has_light_soup or bundle.has_soup_meal
                    local_sum = state.local_score_sum + bundle.local_score
                    partial_budget = None
                    if budget and budget > 0:
                        completed_ratio = sum(meal_targets[m].kcal for m in remaining_meals[:len(state.bundles) + 1]) / max(remaining.kcal, 1)
                        partial_budget = budget * min(completed_ratio, 1.0)
                    score = (
                        nutrient_penalty(n, processed_target)
                        + local_sum * 0.28 + repeat_count * 2.3
                        + budget_penalty(cost, partial_budget) * 0.35
                    )
                    key = _bin(n, has_light_soup)
                    new_state = _State(
                        state.bundles + (bundle,), n, cost, local_sum,
                        frozenset(state.used_item_ids.union(paid_ids)), repeat_count,
                        has_light_soup,
                    )
                    old = next_states.get(key)
                    if old is None:
                        next_states[key] = new_state
                    else:
                        old_score = (
                            nutrient_penalty(old.nutrients, processed_target)
                            + old.local_score_sum * 0.28 + old.repeat_count * 2.3
                            + budget_penalty(old.cost, partial_budget) * 0.35
                        )
                        if score < old_score:
                            next_states[key] = new_state
            ranked = sorted(
                next_states.values(),
                key=lambda state: nutrient_penalty(state.nutrients, processed_target)
                + state.local_score_sum * 0.28 + state.repeat_count * 2.3,
            )[:beam_width]
            states = {_bin(state.nutrients, state.has_light_soup): state for state in ranked}
            dp_trace.append({
                "meal": meal,
                "greedy_candidates": len(candidates[meal]),
                "transitions": transitions,
                "states_kept": len(states),
                "budget_enforced": enforce_budget,
            })
            if progress_callback:
                progress_callback(
                    f"   ├ {MEAL_LABELS[meal]}{budget_label}："
                    f"探索 {transitions} 个状态转移 → 保留 {len(states)} 个最优状态"
                )
            if not states:
                return []
        return list(states.values())

    dp_trace: list[dict] = []
    if progress_callback:
        progress_callback("🧮 开始动态规划优化（Beam Search）……")
    final_states = run_dp(enforce_budget=bool(budget and budget > 0))
    if not final_states and budget and budget > 0:
        if progress_callback:
            progress_callback("⚠️ 预算内无解，放宽预算约束重新搜索……")
        warnings.append("预算内不存在完整合法方案，已显示最接近预算的超预算方案。")
        final_states = run_dp(enforce_budget=False)
    if not final_states:
        raise ValueError("没有得到完整可推荐方案。")

    if light_mode and regular_remaining:
        light_states = [state for state in final_states if state.has_light_soup]
        if light_states:
            final_states = light_states
        else:
            warnings.append("未找到包含清淡粿条/米粉汤的完整方案，已退化为其他清淡组合。")

    def final_score(state: _State) -> float:
        score = (
            nutrient_penalty(state.nutrients, remaining)
            + state.local_score_sum * 0.34
            + state.repeat_count * 2.6
            + budget_penalty(state.cost, budget) * 10.0
        )
        for bundle in state.bundles:
            score += abs(bundle.nutrients.kcal - meal_targets[bundle.meal].kcal) / max(meal_targets[bundle.meal].kcal, 1) * 0.55
        if light_mode and regular_remaining and not state.has_light_soup:
            score += 20
        return score

    best = min(final_states, key=final_score)
    primary_by_meal = {bundle.meal: bundle for bundle in best.bundles}
    ranked_options = {
        meal: _select_diverse_options(primary_by_meal[meal], candidates[meal], recommendation_count)
        for meal in remaining_meals
    }

    if budget and best.cost > budget:
        warnings.append(f"当前最优合法方案超出预算¥{best.cost - budget:.2f}。")
    elif budget and budget > 0:
        warnings.append(f"方案使用预算的{best.cost / budget * 100:.1f}%，在不超过预算的前提下兼顾营养。")
    if consumed.sodium_mg > daily_target.sodium_mg:
        warnings.append("已吃食物的钠估算已超过参考值，后续应优先少汤汁、少加工肉。")
    if consumed.sugar_g > daily_target.sugar_g:
        warnings.append("已吃食物的糖估算已超过参考值，后续不建议含糖饮品。")

    planned = best.nutrients
    return PlanResult(
        bundles=list(best.bundles),
        ranked_meal_options=ranked_options,
        consumed=consumed,
        planned=planned,
        combined=consumed + planned,
        target=daily_target,
        remaining_target=remaining,
        total_cost=best.cost,
        objective_score=final_score(best),
        budget=budget,
        greedy_trace=greedy_trace,
        dp_trace=list(dp_trace),
        warnings=warnings,
    )
