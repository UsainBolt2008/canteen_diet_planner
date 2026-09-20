from __future__ import annotations
from dataclasses import dataclass
from .config import ACTIVITY_FACTORS, MEAL_RATIOS
from .models import Nutrients


@dataclass(frozen=True)
class TargetResult:
    nutrients: Nutrients
    bmi: float
    bmi_label: str
    bmr: float
    tdee: float


def bmi_label(bmi: float) -> str:
    if bmi < 18.5:
        return "体重过低"
    if bmi < 24:
        return "正常"
    if bmi < 28:
        return "超重"
    return "肥胖"


def calculate_daily_targets(
    sex: str,
    age: int,
    height_cm: float,
    weight_kg: float,
    activity: str,
    goal: str,
) -> TargetResult:
    if sex == "男":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    tdee = bmr * ACTIVITY_FACTORS[activity]
    kcal = max(tdee + {"减脂": -300, "维持": 0, "增肌": 250}[goal], 1200 if sex == "女" else 1500)
    protein = weight_kg * {"减脂": 1.2, "维持": 1.0, "增肌": 1.4}[goal]
    fat = kcal * 0.25 / 9
    carbs = max((kcal - protein * 4 - fat * 9) / 4, kcal * 0.40 / 4)
    bmi = weight_kg / (height_cm / 100) ** 2
    return TargetResult(
        nutrients=Nutrients(kcal, protein, fat, carbs, 25.0, 2000.0, kcal * 0.10 / 4),
        bmi=bmi,
        bmi_label=bmi_label(bmi),
        bmr=bmr,
        tdee=tdee,
    )


def split_remaining_target(remaining: Nutrients, meals: list[str]) -> dict[str, Nutrients]:
    ratio_sum = sum(MEAL_RATIOS[m] for m in meals)
    return {meal: remaining.scale(MEAL_RATIOS[meal] / ratio_sum) for meal in meals}


def split_budget(budget: float | None, meals: list[str]) -> dict[str, float | None]:
    if budget is None or budget <= 0:
        return {meal: None for meal in meals}
    ratio_sum = sum(MEAL_RATIOS[m] for m in meals)
    return {meal: budget * MEAL_RATIOS[meal] / ratio_sum for meal in meals}
