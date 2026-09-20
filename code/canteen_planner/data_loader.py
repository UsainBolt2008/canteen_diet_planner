from __future__ import annotations
from pathlib import Path
import pandas as pd
from .config import NUMERIC_COLUMNS


REQUIRED = {
    "id", "name", "shop", "location", "category",
    "price_dinein", "price_takeout", "kcal", "protein_g", "fat_g",
    "carbs_g", "fiber_g", "sodium_mg", "sugar_g",
    "available_breakfast", "available_lunch", "available_dinner",
    "item_role", "standalone_allowed", "meal_anchor",
    "provides_group", "requires_group", "choice_group",
    "package_fee_per_order", "delivery_fee_per_order",
    "preference_categories", "is_light", "light_anchor", "soup_meal",
    "soup_priority", "counts_for_preference", "auto_attach_scope",
    "auto_attach_value", "movement_counted",
}


def load_menu(path: str | Path = "data/canteen_menu_final.csv") -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"未找到算法数据文件：{path}")
    df = pd.read_csv(path, encoding="utf-8-sig", keep_default_na=False)
    missing = sorted(REQUIRED - set(df.columns))
    if missing:
        raise ValueError("算法数据缺少字段：" + ", ".join(missing))

    for column in NUMERIC_COLUMNS:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)

    for column in (
        "id", "name", "shop", "location", "category", "item_role",
        "component_type", "shop_mode", "provides_group", "requires_group",
        "choice_group", "rule_note", "tags", "preference_categories",
        "auto_attach_scope", "auto_attach_value",
    ):
        df[column] = df[column].astype(str).str.strip()

    if df["id"].duplicated().any():
        duplicates = df.loc[df["id"].duplicated(), "id"].tolist()
        raise ValueError(f"数据存在重复ID：{duplicates[:5]}")
    return df
