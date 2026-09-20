MEAL_LABELS = {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐"}
MEAL_RATIOS = {"breakfast": 0.28, "lunch": 0.37, "dinner": 0.35}
PREFERENCE_CATEGORIES = ["主食", "荤菜", "素菜", "汤", "饮品"]

ACTIVITY_FACTORS = {
    "久坐（很少运动）": 1.20,
    "轻度活动（每周1-3次）": 1.375,
    "中度活动（每周3-5次）": 1.55,
    "高强度活动（每周6-7次）": 1.725,
}

SOURCE_LINKS = {
    "中国居民膳食指南（2022）": "https://dg.cnsoc.org/",
    "国家卫生健康委员会成人体重判定标准": "https://www.nhc.gov.cn/wjw/yingyang/201308/a233d450fdbc47c5ad4f08b7e394d1e8.shtml",
    "Mifflin–St Jeor能量预测公式原始论文": "https://pubmed.ncbi.nlm.nih.gov/2305711/",
    "WHO健康膳食建议": "https://www.who.int/news-room/fact-sheets/detail/healthy-diet",
    "WHO钠摄入建议": "https://www.who.int/news-room/fact-sheets/detail/sodium-reduction",
}

NUMERIC_COLUMNS = [
    "price", "price_dinein", "price_takeout", "min_order",
    "portion_g", "kcal", "protein_g", "fat_g", "carbs_g", "fiber_g",
    "sodium_mg", "sugar_g", "is_fried", "is_drink",
    "available_breakfast", "available_lunch", "available_dinner",
    "dinein_available", "takeout_available", "standalone_allowed",
    "meal_anchor", "complete_meal", "choice_min", "choice_max",
    "package_fee_per_order", "delivery_fee_per_order",
    "is_light", "light_anchor", "soup_meal", "soup_priority",
    "counts_for_preference", "movement_counted",
]

DP_BINS = {
    "kcal": 80.0,
    "protein_g": 6.0,
    "fat_g": 5.0,
    "carbs_g": 12.0,
    "fiber_g": 3.0,
}
