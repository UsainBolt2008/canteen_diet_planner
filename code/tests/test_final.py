from pathlib import Path

import pandas as pd

from canteen_planner.data_loader import load_menu
from canteen_planner.meal_candidates import bundle_cost, generate_candidates, make_bundle
from canteen_planner.optimizer import optimize_plan
from canteen_planner.models import Nutrients

DATA = Path("data/canteen_menu_final.csv")


def test_rice_price_is_confirmed_08():
    menu = load_menu(DATA)
    rice = menu[menu["id"].isin(["V0001", "V0002"])]
    assert len(rice) == 2
    assert rice["price_dinein"].eq(0.8).all()
    assert rice["price_takeout"].eq(0.8).all()


def test_free_soup_is_dinein_only_and_not_preference_soup():
    menu = load_menu(DATA)
    free = menu[menu["item_role"].eq("auto_free")]
    assert len(free) == 4
    assert free["takeout_available"].eq(0).all()
    assert free["counts_for_preference"].eq(0).all()
    assert free["movement_counted"].eq(0).all()


def test_first_canteen_bundle_gets_free_soup_but_takeout_does_not():
    menu = load_menu(DATA)
    row = menu[menu["id"].eq("D0172")]
    target = Nutrients(500, 20, 15, 70, 6, 700, 15)
    dinein = make_bundle(
        row, menu, "lunch", "堂食", "经济型", target, "balance",
        {"主食"}, False, 20, validate=True,
    )
    assert dinein is not None
    assert "F0001" in dinein.item_ids
    takeout = make_bundle(
        row, menu, "lunch", "外卖", "经济型", target, "balance",
        {"主食"}, False, 20, validate=True,
    )
    assert takeout is not None
    assert "F0001" not in takeout.item_ids


def test_guangshi_delivery_has_zero_package_fee():
    menu = load_menu(DATA)
    rows = menu[menu["id"].isin(["D0624", "D0636"])]
    total, subtotal, package_fee, delivery_fee = bundle_cost(rows, "外卖", enforce_min_order=False)
    assert package_fee == 0
    assert delivery_fee == 1.2


def test_soup_preference_ranks_wanxiang_high():
    menu = load_menu(DATA)
    target = Nutrients(650, 28, 20, 85, 8, 800, 15)
    candidates, _ = generate_candidates(
        menu, "lunch", target, "堂食", "经济型",
        desired_categories={"汤"}, target_budget=18, max_candidates=30,
    )
    assert candidates
    assert candidates[0].soup_priority >= 2
    assert any(shop == "万象粿条" for shop in candidates[0].shops)


def test_light_mode_requires_a_light_soup_in_remaining_regular_meals():
    menu = load_menu(DATA)
    result = optimize_plan(
        menu=menu,
        daily_target=Nutrients(1900, 85, 55, 260, 25, 2000, 45),
        consumed=Nutrients(450, 18, 12, 65, 5, 450, 8),
        remaining_meals=["lunch", "dinner"],
        service_mode="堂食",
        preference="便利型",
        budget=40,
        desired_categories={"主食", "汤"},
        light_mode=True,
        recommendation_count=3,
        beam_width=250,
    )
    assert any(bundle.has_soup_meal for bundle in result.bundles)
    assert all(1 <= len(result.ranked_meal_options[meal]) <= 3 for meal in ["lunch", "dinner"])
    assert result.total_cost <= 40


def test_budget_is_upper_bound_when_feasible():
    menu = load_menu(DATA)
    result = optimize_plan(
        menu=menu,
        daily_target=Nutrients(1700, 75, 50, 230, 25, 2000, 42),
        consumed=Nutrients(1050, 45, 30, 140, 12, 1000, 20),
        remaining_meals=["dinner"],
        service_mode="堂食",
        preference="经济型",
        budget=18,
        desired_categories={"主食", "荤菜", "素菜"},
        recommendation_count=6,
        beam_width=200,
    )
    assert result.total_cost <= 18
    assert 1 <= len(result.ranked_meal_options["dinner"]) <= 6


from canteen_planner.drinks import recommend_drinks


def test_drink_recommendation_prefers_affordable_mixue():
    menu = load_menu(DATA)
    drinks, warnings = recommend_drinks(
        menu=menu,
        target=Nutrients(2000, 85, 60, 260, 25, 2000, 50),
        current=Nutrients(1500, 65, 42, 190, 15, 1400, 20),
        service_mode="堂食",
        budget_left=12,
        count=5,
    )
    assert drinks
    assert any("蜜雪冰城" in bundle.shops for bundle in drinks[:3])
    assert drinks[0].total_cost <= 8


def test_meal_candidates_do_not_include_drinks_when_drink_category_selected():
    menu = load_menu(DATA)
    candidates, _ = generate_candidates(
        menu, "dinner", Nutrients(650, 28, 20, 85, 8, 800, 15),
        "堂食", "经济型", desired_categories={"主食", "饮品"},
        target_budget=25, max_candidates=20,
    )
    assert candidates
    drink_ids = set(menu[menu["is_drink"].eq(1)]["id"].astype(str))
    assert all(not drink_ids.intersection(bundle.item_ids) for bundle in candidates)
