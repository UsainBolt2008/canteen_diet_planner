from __future__ import annotations
import pandas as pd


def selected_provides(rows: pd.DataFrame) -> set[str]:
    return {value for value in rows["provides_group"].astype(str) if value}


def validate_bundle(rows: pd.DataFrame, menu: pd.DataFrame, meal: str, service_mode: str) -> tuple[bool, str]:
    if rows.empty:
        return False, "空组合"
    rows = rows[~rows["item_role"].eq("auto_free")]
    availability = {"breakfast": "available_breakfast", "lunch": "available_lunch", "dinner": "available_dinner"}[meal]
    if not rows[availability].eq(1).all():
        return False, "包含该餐次不营业商品"
    service_column = "dinein_available" if service_mode == "堂食" else "takeout_available"
    if not rows[service_column].eq(1).all():
        return False, "包含当前服务方式不可用商品"
    if not rows["meal_anchor"].eq(1).any():
        return False, "没有主餐锚点"

    for _, group in rows.groupby("shop"):
        if group["shop_mode"].eq("custom_mix").any():
            if len(group) < 2 or not group["component_type"].eq("staple").any():
                return False, "自选麻辣烫至少需要主食和另一项食材"

    provides = selected_provides(rows)
    for _, item in rows[rows["requires_group"].astype(str).ne("")].iterrows():
        if item["requires_group"] not in provides:
            return False, f"{item['name']}缺少同店基础商品"

    for provider in provides:
        rules = menu[
            menu["requires_group"].eq(provider)
            & menu["choice_group"].astype(str).ne("")
            & menu["choice_min"].gt(0)
        ]
        for choice_group, group in rules.groupby("choice_group"):
            minimum = int(group["choice_min"].max())
            maximum = int(group["choice_max"].max())
            count = int(rows["choice_group"].eq(choice_group).sum())
            if count < minimum:
                return False, f"缺少必选项：{choice_group}"
            if maximum > 0 and count > maximum:
                return False, f"超过可选数量：{choice_group}"
    return True, ""


def validate_consumed_selection(rows: pd.DataFrame) -> list[str]:
    if rows.empty:
        return []
    warnings: list[str] = []
    provides = selected_provides(rows)
    for _, item in rows[rows["requires_group"].astype(str).ne("")].iterrows():
        if item["requires_group"] not in provides:
            warnings.append(f"{item['name']}属于加料或附属项，但没有同时记录对应基础商品。")
    return warnings
