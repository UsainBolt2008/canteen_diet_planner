from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Nutrients:
    kcal: float = 0.0
    protein_g: float = 0.0
    fat_g: float = 0.0
    carbs_g: float = 0.0
    fiber_g: float = 0.0
    sodium_mg: float = 0.0
    sugar_g: float = 0.0

    def __add__(self, other: "Nutrients") -> "Nutrients":
        return Nutrients(
            self.kcal + other.kcal,
            self.protein_g + other.protein_g,
            self.fat_g + other.fat_g,
            self.carbs_g + other.carbs_g,
            self.fiber_g + other.fiber_g,
            self.sodium_mg + other.sodium_mg,
            self.sugar_g + other.sugar_g,
        )

    def __sub__(self, other: "Nutrients") -> "Nutrients":
        return Nutrients(
            self.kcal - other.kcal,
            self.protein_g - other.protein_g,
            self.fat_g - other.fat_g,
            self.carbs_g - other.carbs_g,
            self.fiber_g - other.fiber_g,
            self.sodium_mg - other.sodium_mg,
            self.sugar_g - other.sugar_g,
        )

    def clip_min(self, value: float = 0.0) -> "Nutrients":
        return Nutrients(
            max(self.kcal, value),
            max(self.protein_g, value),
            max(self.fat_g, value),
            max(self.carbs_g, value),
            max(self.fiber_g, value),
            max(self.sodium_mg, value),
            max(self.sugar_g, value),
        )

    def scale(self, factor: float) -> "Nutrients":
        return Nutrients(
            self.kcal * factor,
            self.protein_g * factor,
            self.fat_g * factor,
            self.carbs_g * factor,
            self.fiber_g * factor,
            self.sodium_mg * factor,
            self.sugar_g * factor,
        )


@dataclass(frozen=True)
class Bundle:
    meal: str
    item_ids: tuple[str, ...]
    item_names: tuple[str, ...]
    shops: tuple[str, ...]
    locations: tuple[str, ...]
    nutrients: Nutrients
    item_subtotal: float
    package_fee: float
    delivery_fee: float
    total_cost: float
    local_score: float
    preference_categories: tuple[str, ...] = ()
    has_light_item: bool = False
    has_soup_meal: bool = False
    soup_priority: int = 0
    explanation: tuple[str, ...] = ()

    @property
    def vendor_count(self) -> int:
        return len(self.shops)

    @property
    def location_count(self) -> int:
        return len(self.locations)


@dataclass
class PlanResult:
    bundles: list[Bundle]
    ranked_meal_options: dict[str, list[Bundle]]
    consumed: Nutrients
    planned: Nutrients
    combined: Nutrients
    target: Nutrients
    remaining_target: Nutrients
    total_cost: float
    objective_score: float
    budget: float | None = None
    greedy_trace: list[dict] = field(default_factory=list)
    dp_trace: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
