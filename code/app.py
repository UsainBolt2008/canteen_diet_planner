# from __future__ import annotations

# import pandas as pd
# import streamlit as st

# from canteen_planner.config import ACTIVITY_FACTORS, MEAL_LABELS, PREFERENCE_CATEGORIES, SOURCE_LINKS
# from canteen_planner.data_loader import load_menu
# from canteen_planner.drinks import recommend_drinks
# from canteen_planner.optimizer import nutrients_from_selected, optimize_plan
# from canteen_planner.models import Bundle, Nutrients
# from canteen_planner.nutrition import calculate_daily_targets
# from canteen_planner.validation import validate_consumed_selection

# # ── page config ──────────────────────────────────────────────────────────────
# st.set_page_config(page_title="Campus Canteen Diet Planner", page_icon="🍱", layout="wide")

# # ── custom CSS ───────────────────────────────────────────────────────────────
# st.markdown("""
# <style>
#     /* ── global ── */
#     .stApp { font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; }

#     /* ── metric cards ── */
#     .metric-row [data-testid="stMetric"] {
#         background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
#         border-radius: 12px;
#         padding: 12px 16px;
#         border: 1px solid #e2e8f0;
#     }
#     .metric-highlight [data-testid="stMetric"] {
#         background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
#         border: 1px solid #6ee7b7;
#     }

#     /* ── bundle cards ── */
#     .bundle-card {
#         border-left: 4px solid #3b82f6;
#         border-radius: 8px;
#         padding: 16px 20px 12px 20px;
#         margin: 10px 0;
#         background: #f9fafb;
#     }
#     .bundle-card.primary {
#         border-left-color: #10b981;
#         background: linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%);
#     }
#     .bundle-card.over-budget {
#         border-left-color: #f59e0b;
#         background: #fffbeb;
#     }
#     .bundle-card h4 { margin-top: 0; color: #1e293b; }
#     .bundle-card .shop-line { color: #64748b; font-size: 0.9em; }
#     .bundle-card .price { font-weight: 700; color: #0f172a; font-size: 1.1em; }

#     /* ── section headers ── */
#     .section-header {
#         font-size: 1.3em; font-weight: 700; color: #1e293b;
#         border-bottom: 2px solid #3b82f6; padding-bottom: 6px; margin-top: 28px;
#     }

#     /* ── sidebar ── */
#     section[data-testid="stSidebar"] { width: 380px !important; }
#     section[data-testid="stSidebar"][aria-expanded="false"] { width: auto !important; }

#     /* ── tabs ── */
#     [data-testid="stTabs"] button { font-weight: 600; font-size: 1.02em; }

#     /* ── expander ── */
#     [data-testid="stExpander"] summary { font-weight: 600; }

#     /* ── info/warning boxes ── */
#     [data-testid="stAlert"] { border-radius: 8px; }

#     /* ── button ── */
#     [data-testid="baseButton-primary"] {
#         background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
#         font-weight: 700 !important;
#         font-size: 1.05em !important;
#         border-radius: 10px !important;
#         padding: 0.6em 2em !important;
#     }
# </style>
# """, unsafe_allow_html=True)

# # ── cached data loader ───────────────────────────────────────────────────────
# @st.cache_data(ttl=3600, show_spinner="正在加载食堂菜单数据……")
# def cached_load_menu() -> pd.DataFrame:
#     return load_menu()


# menu = cached_load_menu()

# # ── session state init ───────────────────────────────────────────────────────
# if "plan_generated" not in st.session_state:
#     st.session_state.plan_generated = False
#     st.session_state.meal_result = None
#     st.session_state.planned_nutrients = Nutrients()
#     st.session_state.total_cost = 0.0
#     st.session_state.combined = Nutrients()
#     st.session_state.drink_bundles = []
#     st.session_state.drink_warnings = []
#     st.session_state.meal_budget = None
#     st.session_state.consumed_snapshot = Nutrients()
#     st.session_state.target_snapshot = Nutrients()
#     st.session_state.remaining_meals_snapshot = []
#     st.session_state.rec_counts_snapshot = {}
#     st.session_state.last_total_cost = None
#     st.session_state.last_combined_kcal = None


# # ── helpers ──────────────────────────────────────────────────────────────────

# def reserve_for_drink(total_budget: float | None) -> float | None:
#     if total_budget is None or total_budget <= 0:
#         return 10.0
#     return min(12.0, max(3.0, total_budget * 0.2))


# def bundle_rows(bundle: Bundle) -> pd.DataFrame:
#     indexed = menu.set_index("id", drop=False)
#     rows = indexed.loc[list(bundle.item_ids)]
#     if isinstance(rows, pd.Series):
#         rows = rows.to_frame().T
#     return rows.reset_index(drop=True)


# def render_bundle_card(bundle: Bundle, rank: int, primary: bool, title_prefix: str = "") -> None:
#     """Render a single bundle as a styled card with expandable detail table."""
#     title = f"{title_prefix}第{rank}名" + (" · ⭐ 建议选择" if primary else " · 备选")

#     with st.expander(title, expanded=primary):
#         # ── header row: names + price ──
#         col_h, col_p = st.columns([3, 1])
#         with col_h:
#             item_text = "  +  ".join(bundle.item_names)
#             shop_text = "、".join(bundle.shops)
#             location_text = "、".join(bundle.locations)
#             st.markdown(f"**{item_text}**")
#             st.caption(f"🏪 商家：{shop_text}　📍 地点：{location_text}")
#         with col_p:
#             st.metric("💰 费用", f"{bundle.total_cost:.2f} 元")

#         # ── nutrition row ──
#         nc1, nc2, nc3, nc4, nc5 = st.columns(5)
#         nc1.metric("🔥 热量", f"{bundle.nutrients.kcal:.0f} kcal")
#         nc2.metric("🥩 蛋白质", f"{bundle.nutrients.protein_g:.1f} g")
#         nc3.metric("🧈 脂肪", f"{bundle.nutrients.fat_g:.1f} g")
#         nc4.metric("🍚 碳水", f"{bundle.nutrients.carbs_g:.1f} g")
#         nc5.metric("🍬 糖", f"{bundle.nutrients.sugar_g:.1f} g")

#         # ── fee breakdown ──
#         if bundle.package_fee > 0 or bundle.delivery_fee > 0:
#             fc1, fc2, fc3 = st.columns(3)
#             fc1.caption(f"商品小计: {bundle.item_subtotal:.2f} 元")
#             fc2.caption(f"打包费: {bundle.package_fee:.2f} 元")
#             fc3.caption(f"配送费: {bundle.delivery_fee:.2f} 元")

#         # ── detail table ──
#         rows = bundle_rows(bundle)
#         display = rows[["name", "shop", "location", "price_dinein", "price_takeout",
#                          "kcal", "protein_g", "fat_g", "carbs_g", "sugar_g"]].copy()
#         display.columns = ["Item", "Shop", "Location", "Dine-in 元", "Takeout 元",
#                            "kcal", "Protein(g)", "Fat(g)", "Carbs(g)", "Sugar(g)"]
#         st.markdown("**📋 明细表**")
#         st.dataframe(display, hide_index=True, use_container_width=True)

#         # ── explanation ──
#         if bundle.explanation:
#             st.info("📝 " + "；".join(bundle.explanation) + "。")


# def nutrient_chart(consumed_nutrients: Nutrients, combined_nutrients: Nutrients, target: Nutrients) -> pd.DataFrame:
#     return pd.DataFrame({
#         "Metric": ["Energy", "Protein", "Fat", "Carbohydrate", "Fiber", "Sodium", "Sugar"],
#         "已摄入 (%)": [
#             consumed_nutrients.kcal / max(target.kcal, 1) * 100,
#             consumed_nutrients.protein_g / max(target.protein_g, 1) * 100,
#             consumed_nutrients.fat_g / max(target.fat_g, 1) * 100,
#             consumed_nutrients.carbs_g / max(target.carbs_g, 1) * 100,
#             consumed_nutrients.fiber_g / max(target.fiber_g, 1) * 100,
#             consumed_nutrients.sodium_mg / max(target.sodium_mg, 1) * 100,
#             consumed_nutrients.sugar_g / max(target.sugar_g, 1) * 100,
#         ],
#         "规划后 (%)": [
#             combined_nutrients.kcal / max(target.kcal, 1) * 100,
#             combined_nutrients.protein_g / max(target.protein_g, 1) * 100,
#             combined_nutrients.fat_g / max(target.fat_g, 1) * 100,
#             combined_nutrients.carbs_g / max(target.carbs_g, 1) * 100,
#             combined_nutrients.fiber_g / max(target.fiber_g, 1) * 100,
#             combined_nutrients.sodium_mg / max(target.sodium_mg, 1) * 100,
#             combined_nutrients.sugar_g / max(target.sugar_g, 1) * 100,
#         ],
#     }).set_index("Metric")


# def render_radar_chart(consumed: Nutrients, combined: Nutrients, target: Nutrients) -> None:
#     """Plotly radar chart comparing nutrition percentages against targets."""
#     try:
#         import plotly.graph_objects as go  # type: ignore[import-unresolved]
#     except ImportError:
#         st.warning("📦 需要安装 plotly 以显示雷达图：`pip install plotly`")
#         return

#     categories = ["热量", "蛋白质", "脂肪", "碳水", "纤维", "钠", "糖"]

#     def _pct(n: Nutrients) -> list[float]:
#         return [
#             min(n.kcal / max(target.kcal, 1) * 100, 150),
#             min(n.protein_g / max(target.protein_g, 1) * 100, 150),
#             min(n.fat_g / max(target.fat_g, 1) * 100, 150),
#             min(n.carbs_g / max(target.carbs_g, 1) * 100, 150),
#             min(n.fiber_g / max(target.fiber_g, 1) * 100, 150),
#             min(n.sodium_mg / max(target.sodium_mg, 1) * 100, 150),
#             min(n.sugar_g / max(target.sugar_g, 1) * 100, 150),
#         ]

#     fig = go.Figure()
#     fig.add_trace(go.Scatterpolar(
#         r=_pct(consumed), theta=categories, fill="toself",
#         name="已摄入", line=dict(color="#f59e0b", width=2),
#         fillcolor="rgba(245,158,11,0.15)",
#     ))
#     fig.add_trace(go.Scatterpolar(
#         r=_pct(combined), theta=categories, fill="toself",
#         name="规划后", line=dict(color="#3b82f6", width=2),
#         fillcolor="rgba(59,130,246,0.2)",
#     ))
#     fig.add_trace(go.Scatterpolar(
#         r=[100] * 7, theta=categories, fill="none",
#         name="目标 (100%)", line=dict(color="#10b981", width=2, dash="dash"),
#     ))

#     fig.update_layout(
#         polar=dict(radialaxis=dict(visible=True, range=[0, 150], ticksuffix="%")),
#         showlegend=True, legend=dict(orientation="h", y=-0.12),
#         margin=dict(l=40, r=40, t=20, b=60),
#         height=400,
#     )
#     st.plotly_chart(fig, use_container_width=True)


# def render_algorithm_trace(greedy_trace: list[dict], dp_trace: list[dict]) -> None:
#     """Visualize the optimization algorithm's internal steps."""
#     if not greedy_trace and not dp_trace:
#         return

#     with st.expander("🧾 推荐生成概览", expanded=False):
#         st.markdown("#### 🔍 可选方案统计")
#         if greedy_trace:
#             trace_df = pd.DataFrame(greedy_trace)
#             trace_display = trace_df.rename(columns={
#                 "meal": "餐次", "shop": "商家",
#                 "legal_single_shop_candidates": "合法候选数",
#             })
#             trace_display["餐次"] = trace_display["餐次"].map(MEAL_LABELS)
#             st.dataframe(
#                 trace_display[["餐次", "商家", "合法候选数"]],
#                 hide_index=True, use_container_width=True,
#             )
#             st.caption(f"共 {len(greedy_trace)} 家商家参与候选生成，"
#                        f"合计产出 {trace_display['合法候选数'].sum()} 个候选套餐。")

#         st.markdown("#### 🧮 最终筛选统计")
#         if dp_trace:
#             dp_df = pd.DataFrame(dp_trace)
#             dp_df["meal_label"] = dp_df["meal"].map(MEAL_LABELS)

#             # ── metrics row ──
#             mc1, mc2, mc3 = st.columns(3)
#             total_transitions = int(dp_df["transitions"].sum())
#             total_greedy = int(dp_df["greedy_candidates"].sum())
#             mc1.metric("总状态转移次数", total_transitions)
#             mc2.metric("候选套餐总数", total_greedy)
#             mc3.metric("最终保留状态", int(dp_df["states_kept"].iloc[-1]) if not dp_df.empty else 0)

#             # ── line chart: states and transitions per meal ──
#             chart_data = dp_df.set_index("meal_label")[["states_kept", "transitions"]].copy()
#             chart_data.columns = ["保留状态数", "转移次数"]
#             st.line_chart(chart_data, use_container_width=True)

#             extra_note = " 首轮预算内无合适方案，系统已自动放宽预算限制。" if any(
#                 not step.get("budget_enforced", True) for step in dp_trace
#             ) else ""
#             st.caption("系统会综合比较各餐候选方案，并保留更符合营养、预算和偏好的结果。" + extra_note)


# def render_plan_comparison(
#     meal_result, remaining_meals: list[str], recommendation_counts: dict,
# ) -> None:
#     """Render a cross-meal comparison table of top-ranked bundles."""
#     st.markdown('<p class="section-header">📊 方案对比总览</p>', unsafe_allow_html=True)

#     rows = []
#     for meal in remaining_meals:
#         for rank, bundle in enumerate(
#             meal_result.ranked_meal_options[meal][:recommendation_counts[meal]], start=1
#         ):
#             rows.append({
#                 "餐次": MEAL_LABELS[meal],
#                 "排名": rank,
#                 "推荐": "⭐" if rank == 1 else "",
#                 "内容": " + ".join(bundle.item_names),
#                 "商家": "、".join(bundle.shops),
#                 "费用": f"{bundle.total_cost:.2f} 元",
#                 "热量": f"{bundle.nutrients.kcal:.0f} kcal",
#                 "蛋白质": f"{bundle.nutrients.protein_g:.1f}g",
#                 "偏好覆盖": "、".join(bundle.preference_categories) if bundle.preference_categories else "—",
#             })

#     if rows:
#         comp_df = pd.DataFrame(rows)
#         st.dataframe(comp_df, hide_index=True, use_container_width=True,
#                      column_config={
#                          "推荐": st.column_config.TextColumn(width="small"),
#                          "内容": st.column_config.TextColumn(width="large"),
#                      })


# def render_nutrient_bars(consumed: Nutrients, target: Nutrients) -> None:
#     """Render HTML nutrient progress bars with color coding."""
#     nutrients_list = [
#         ("🔥 热量", consumed.kcal, target.kcal, "kcal"),
#         ("🥩 蛋白质", consumed.protein_g, target.protein_g, "g"),
#         ("🧈 脂肪", consumed.fat_g, target.fat_g, "g"),
#         ("🍚 碳水", consumed.carbs_g, target.carbs_g, "g"),
#         ("🌾 纤维", consumed.fiber_g, target.fiber_g, "g"),
#         ("🧂 钠", consumed.sodium_mg, target.sodium_mg, "mg"),
#         ("🍬 糖", consumed.sugar_g, target.sugar_g, "g"),
#     ]
#     for label, value, target_val, unit in nutrients_list:
#         pct = min(value / max(target_val, 1) * 100, 150)
#         if pct < 80:
#             color, bg = "#ef4444", "#fef2f2"
#         elif pct <= 100:
#             color, bg = "#10b981", "#ecfdf5"
#         else:
#             color, bg = "#f59e0b", "#fffbeb"
#         st.markdown(f"""
#         <div style="display:flex;align-items:center;margin:4px 0;padding:6px 10px;
#                     background:{bg};border-radius:6px;font-size:0.9em">
#             <span style="width:90px;font-weight:600">{label}</span>
#             <div style="flex:1;margin:0 10px">
#                 <div style="background:#e5e7eb;border-radius:3px;height:8px;width:100%">
#                     <div style="width:{min(pct, 100):.0f}%;background:{color};height:8px;border-radius:3px"></div>
#                 </div>
#             </div>
#             <span style="width:130px;text-align:right;color:#64748b">
#                 {value:.1f} / {target_val:.0f} {unit} ({pct:.0f}%)
#             </span>
#         </div>
#         """, unsafe_allow_html=True)


# # ══════════════════════════════════════════════════════════════════════════════
# # SIDEBAR
# # ══════════════════════════════════════════════════════════════════════════════

# with st.sidebar:
#     st.markdown("## 🍱 饮食规划")

#     tab_user, tab_log, tab_settings = st.tabs(["👤 用户信息", "📝 今日记录", "⚙️ 规划设置"])

#     # ── Tab 1: User Info ──
#     with tab_user:
#         sex = st.radio("性别", ["男", "女"], horizontal=True, key="sex")
#         col_a1, col_a2 = st.columns(2)
#         with col_a1:
#             age = st.number_input("年龄", 14, 100, 20, key="age")
#         with col_a2:
#             height = st.number_input("身高（cm）", 120.0, 220.0, 170.0, 1.0, key="height")
#         weight = st.number_input("体重（kg）", 30.0, 200.0, 60.0, 0.5, key="weight")
#         activity = st.selectbox("活动水平", list(ACTIVITY_FACTORS), key="activity")
#         goal = st.selectbox("饮食目标", ["维持", "减脂", "增肌"], key="goal")

#     # ── Tab 2: Today's Record ──
#     with tab_log:
#         ate_breakfast = st.checkbox("已吃早餐", value=False, key="ate_breakfast")
#         ate_lunch = st.checkbox("已吃午餐", value=False, key="ate_lunch")
#         ate_dinner = st.checkbox("已吃晚餐", value=False, key="ate_dinner")

#     # ── Tab 3: Plan Settings ──
#     with tab_settings:
#         service_mode = st.radio("就餐方式", ["堂食", "外卖"], horizontal=True, key="service_mode")
#         if service_mode == "堂食":
#             preference = st.radio("堂食偏好", ["经济型", "便利型"], horizontal=True, key="preference")
#         else:
#             preference = "经济型"
#             st.info("外卖按每家店计算一次打包费和配送费。")

#         budget = st.number_input("剩余总预算（元，0表示不限）", 0.0, 300.0, 40.0, 1.0, key="budget")

#         st.caption("各餐推荐方案数")
#         rc1, rc2, rc3, rc4 = st.columns(4)
#         with rc1:
#             breakfast_recommendation_count = st.number_input("早餐", 1, 6, 3, 1, key="brc")
#         with rc2:
#             lunch_recommendation_count = st.number_input("午餐", 1, 6, 3, 1, key="lrc")
#         with rc3:
#             dinner_recommendation_count = st.number_input("晚餐", 1, 6, 3, 1, key="drc")
#         with rc4:
#             drink_recommendation_count = st.number_input("饮品", 1, 6, 3, 1, key="drkc")

#         desired_categories = set(st.multiselect(
#             "希望推荐的类别",
#             PREFERENCE_CATEGORIES,
#             default=["主食", "荤菜", "素菜"],
#             help="饮品会单独推荐，不会混入早餐、午餐或晚餐。",
#             key="desired_categories",
#         ))
#         c1, c2 = st.columns(2)
#         with c1:
#             avoid_fried = st.checkbox("避免油炸食品", value=False, key="avoid_fried")
#         with c2:
#             light_mode = st.checkbox("偏好清淡", value=False, key="light_mode")

# # ── derived state (not in tabs, always computed) ──
# meal_states = {"breakfast": ate_breakfast, "lunch": ate_lunch, "dinner": ate_dinner}
# consumed_meals = [meal for meal, eaten in meal_states.items() if eaten]
# remaining_meals = [meal for meal, eaten in meal_states.items() if not eaten]
# wants_drink = "饮品" in desired_categories
# meal_desired_categories = desired_categories - {"饮品"}
# recommendation_counts = {
#     "breakfast": int(breakfast_recommendation_count),
#     "lunch": int(lunch_recommendation_count),
#     "dinner": int(dinner_recommendation_count),
# }

# # ══════════════════════════════════════════════════════════════════════════════
# # MAIN AREA
# # ══════════════════════════════════════════════════════════════════════════════

# st.title("🍱 校园食堂饮食规划系统")
# st.caption("根据个人信息、今日已吃内容、预算和食堂菜单，给出正餐与饮品建议。")

# # ── compute targets ──
# result_target = calculate_daily_targets(sex, int(age), float(height), float(weight), activity, goal)

# # ── consumed food selection ──
# selections: dict[str, float] = {}

# if consumed_meals:
#     st.markdown('<p class="section-header">📝 记录已经吃过的食物</p>', unsafe_allow_html=True)
#     for meal in consumed_meals:
#         availability = {"breakfast": "available_breakfast", "lunch": "available_lunch", "dinner": "available_dinner"}[meal]
#         options_df = menu[menu[availability].eq(1) & ~menu["item_role"].eq("auto_free")].copy()
#         # ── food search ──
#         search_term = st.text_input(
#             f"🔍 搜索{MEAL_LABELS[meal]}食物（按名称/商家/地点）",
#             key=f"search_{meal}", placeholder="输入关键词过滤……",
#         )
#         if search_term:
#             term = search_term.lower()
#             options_df = options_df[
#                 options_df["name"].str.lower().str.contains(term, na=False)
#                 | options_df["shop"].str.lower().str.contains(term, na=False)
#                 | options_df["location"].str.lower().str.contains(term, na=False)
#             ]
#             if options_df.empty:
#                 st.caption(f"没有匹配「{search_term}」的食物，请尝试其他关键词。")
#         labels = {row["id"]: f'{row["name"]}｜{row["shop"]}｜{row["location"]}' for _, row in options_df.iterrows()}
#         selected = st.multiselect(
#             f"{MEAL_LABELS[meal]}吃了什么？（{len(options_df)} 项）",
#             options_df["id"].tolist(),
#             format_func=lambda item_id, mapping=labels: mapping.get(item_id, item_id),
#             key=f"selected_{meal}",
#         )
#         for item_id in selected:
#             selections[item_id] = float(st.number_input(
#                 f"{labels[item_id]}：份数", 0.25, 5.0, 1.0, 0.25,
#                 key=f"servings_{meal}_{item_id}",
#             ))

# consumed = nutrients_from_selected(menu, selections)
# if selections:
#     for warning in validate_consumed_selection(menu[menu["id"].isin(selections)]):
#         st.warning(warning)

# # ── nutrition dashboard ──
# st.markdown('<p class="section-header">📈 营养概览</p>', unsafe_allow_html=True)
# bmi_col, bars_col = st.columns([1, 2])
# with bmi_col:
#     bmi_val = result_target.bmi
#     bmi_color = "#10b981" if 18.5 <= bmi_val < 24 else ("#f59e0b" if bmi_val < 28 else "#ef4444")
#     st.markdown(f"""
#     <div style="text-align:center;padding:16px 8px;background:linear-gradient(135deg,#f8fafc,#e2e8f0);
#                 border-radius:12px;border:1px solid #e2e8f0">
#         <div style="font-size:0.85em;color:#64748b;margin-bottom:4px">BMI 指数</div>
#         <div style="font-size:2.4em;font-weight:800;color:{bmi_color}">{bmi_val:.1f}</div>
#         <div style="font-size:0.9em;color:{bmi_color};font-weight:600">{result_target.bmi_label}</div>
#         <div style="font-size:0.75em;color:#94a3b8;margin-top:4px">
#             目标 {result_target.nutrients.kcal:.0f} kcal · 蛋白质 {result_target.nutrients.protein_g:.0f}g
#         </div>
#     </div>
#     """, unsafe_allow_html=True)
# with bars_col:
#     if consumed.kcal > 0:
#         render_nutrient_bars(consumed, result_target.nutrients)
#     else:
#         st.info("👆 在侧边栏记录已吃食物后，这里会显示营养摄入进度。")

# with st.expander("📖 查看基础规则"):
#     st.write("早餐仅从早餐开放窗口推荐；午餐和晚餐从正餐开放窗口推荐。")
#     st.write("加料、免费配菜和必选米饭不能单独购买。")
#     st.write("堂食符合条件时会显示免费例汤，免费例汤营养价值较低。")
#     st.write("饮品和冰淇淋单独推荐，不会混入正餐套餐。")

# # ── empty-state guide ──
# if not st.session_state.plan_generated:
#     st.info("👆 在侧边栏填写个人信息和规划设置，然后点击下方按钮即可获得个性化饮食方案。")

# # ══════════════════════════════════════════════════════════════════════════════
# # GENERATE BUTTON
# # ══════════════════════════════════════════════════════════════════════════════

# if st.button("🚀 生成饮食建议", type="primary", use_container_width=True):
#     planned_nutrients = Nutrients()
#     total_cost = 0.0
#     meal_result = None
#     drink_bundles = []
#     drink_warnings = []
#     meal_budget = None if budget <= 0 else float(budget)
#     if wants_drink and budget > 0:
#         meal_budget = max(0.0, float(budget) - float(reserve_for_drink(float(budget)) or 0.0))

#     # ── Meal Planning with real-time status ──
#     if remaining_meals:
#         try:
#             with st.status("🍳 正在生成饮食建议……", expanded=True) as status_ctx:
#                 def on_progress(msg: str) -> None:
#                     status_ctx.write(msg)

#                 meal_result = optimize_plan(
#                     menu=menu,
#                     daily_target=result_target.nutrients,
#                     consumed=consumed,
#                     remaining_meals=remaining_meals,
#                     service_mode=service_mode,
#                     preference=preference,
#                     budget=meal_budget,
#                     avoid_fried=avoid_fried,
#                     desired_categories=meal_desired_categories,
#                     light_mode=light_mode,
#                     recommendation_count=max(recommendation_counts[meal] for meal in remaining_meals),
#                     progress_callback=on_progress,
#                 )
#                 status_ctx.update(label="✅ 正餐规划完成！", state="complete")
#         except ValueError as exc:
#             st.error(str(exc))
#             st.session_state.plan_generated = False
#             st.stop()

#         planned_nutrients = meal_result.planned
#         total_cost = meal_result.total_cost
#     else:
#         meal_result = None
#         st.info("三餐都已记录，本次不再规划正餐。")

#     # ── Drink edge case: need consumed records ──
#     if wants_drink and not selections:
#         st.warning("请先记录今天已经吃过的食物，再生成饮品或冰淇淋建议。")

#     # ── Drink Recommendations ──
#     if wants_drink and selections:
#         current_after_meals = consumed + planned_nutrients
#         budget_left = None if budget <= 0 else max(float(budget) - total_cost, 0.0)
#         with st.status("🥤 正在分析饮品与冰淇淋建议……", expanded=True) as drink_status:
#             drink_bundles, drink_warnings = recommend_drinks(
#                 menu=menu,
#                 target=result_target.nutrients,
#                 current=current_after_meals,
#                 service_mode=service_mode,
#                 budget_left=budget_left,
#                 count=int(drink_recommendation_count),
#             )
#             drink_status.update(label=f"✅ 饮品分析完成！共 {len(drink_bundles)} 个推荐", state="complete")
#         if drink_bundles:
#             planned_nutrients = planned_nutrients + drink_bundles[0].nutrients
#             total_cost += drink_bundles[0].total_cost

#     # ── Store in session state ──
#     combined = consumed + planned_nutrients
#     # save previous for comparison
#     if st.session_state.total_cost and st.session_state.total_cost > 0:
#         st.session_state.last_total_cost = st.session_state.total_cost
#         st.session_state.last_combined_kcal = st.session_state.combined.kcal
#     st.session_state.plan_generated = True
#     st.session_state.meal_result = meal_result
#     st.session_state.planned_nutrients = planned_nutrients
#     st.session_state.total_cost = total_cost
#     st.session_state.combined = combined
#     st.session_state.meal_budget = meal_budget
#     st.session_state.drink_bundles = drink_bundles
#     st.session_state.drink_warnings = drink_warnings
#     st.session_state.consumed_snapshot = consumed
#     st.session_state.target_snapshot = result_target.nutrients
#     st.session_state.remaining_meals_snapshot = remaining_meals
#     st.session_state.rec_counts_snapshot = recommendation_counts

# # ══════════════════════════════════════════════════════════════════════════════
# # RESULTS (persisted via session_state)
# # ══════════════════════════════════════════════════════════════════════════════

# if st.session_state.plan_generated and st.session_state.meal_result is not None:
#     meal_result = st.session_state.meal_result
#     planned_nutrients = st.session_state.planned_nutrients
#     total_cost = st.session_state.total_cost
#     combined = st.session_state.combined
#     meal_budget = st.session_state.meal_budget
#     drink_bundles = st.session_state.drink_bundles
#     drink_warnings = st.session_state.drink_warnings
#     consumed_snap = st.session_state.consumed_snapshot
#     target_snap = st.session_state.target_snapshot
#     stored_remaining = st.session_state.remaining_meals_snapshot
#     stored_recs = st.session_state.rec_counts_snapshot

#     # ── history delta ──
#     if st.session_state.last_total_cost is not None:
#         delta_cost = total_cost - st.session_state.last_total_cost
#         delta_kcal = combined.kcal - st.session_state.last_combined_kcal
#         st.caption(
#             f"📊 与上次对比：费用 {delta_cost:+.2f} 元　｜　"
#             f"热量 {delta_kcal:+.0f} kcal"
#         )

#     # ── results header ──
#     st.markdown('<p class="section-header">🍽️ 规划结果</p>', unsafe_allow_html=True)
#     top = st.columns(5)
#     top[0].metric("正餐费用", f"{total_cost:.2f} 元")
#     top[1].metric("正餐预算", "不限" if meal_budget is None else f"{meal_budget:.2f} 元")
#     utilization = 0 if not meal_budget else total_cost / meal_budget * 100
#     top[2].metric("预算使用率", "—" if not meal_budget else f"{utilization:.1f}%")
#     top[3].metric("规划餐次", len(meal_result.bundles))
#     top[4].metric("规划后热量", f"{combined.kcal:.0f} kcal")

#     # ── algorithm trace (collapsed) ──
#     render_algorithm_trace(meal_result.greedy_trace, meal_result.dp_trace)

#     # ── plan comparison table ──
#     render_plan_comparison(meal_result, stored_remaining, stored_recs)

#     # ── per-meal bundles ──
#     st.markdown('<p class="section-header">🍱 正餐建议</p>', unsafe_allow_html=True)
#     for meal in stored_remaining:
#         st.subheader(MEAL_LABELS[meal])
#         for rank, bundle in enumerate(
#             meal_result.ranked_meal_options[meal][:stored_recs[meal]], start=1
#         ):
#             render_bundle_card(bundle, rank, primary=(rank == 1))

#     for warning in meal_result.warnings:
#         st.warning(warning)

#     # ── Drink Recommendations ──
#     if drink_bundles:
#         st.markdown('<p class="section-header">🥤 饮品与冰淇淋建议</p>', unsafe_allow_html=True)
#         for rank, bundle in enumerate(drink_bundles, start=1):
#             render_bundle_card(bundle, rank, primary=(rank == 1), title_prefix="饮品")
#         for warning in drink_warnings:
#             st.warning(warning)

#     # ── Final Nutrition Summary ──
#     st.markdown('<p class="section-header">📊 营养完成度</p>', unsafe_allow_html=True)
#     chart_col, radar_col = st.columns([1, 1])
#     with chart_col:
#         st.markdown("##### 柱状图对比")
#         st.bar_chart(nutrient_chart(consumed_snap, combined, target_snap))
#     with radar_col:
#         st.markdown("##### 雷达图")
#         render_radar_chart(consumed_snap, combined, target_snap)

#     st.metric("💰 本次建议总费用", f"{total_cost:.2f} 元")

#     # ── export ──
#     export_lines = ["校园食堂饮食规划方案", "=" * 30, ""]
#     for meal in stored_remaining:
#         export_lines.append(f"【{MEAL_LABELS[meal]}】")
#         for rank, bundle in enumerate(meal_result.ranked_meal_options[meal][:stored_recs[meal]], start=1):
#             star = "⭐" if rank == 1 else "  "
#             export_lines.append(f"  {star} 第{rank}名: {' + '.join(bundle.item_names)}")
#             export_lines.append(f"      商家: {'、'.join(bundle.shops)}  费用: {bundle.total_cost:.2f} 元")
#             export_lines.append(f"      热量: {bundle.nutrients.kcal:.0f} kcal  蛋白质: {bundle.nutrients.protein_g:.1f}g")
#     if drink_bundles:
#         export_lines.append("")
#         export_lines.append("【饮品】")
#         for rank, bundle in enumerate(drink_bundles, start=1):
#             export_lines.append(f"  第{rank}名: {bundle.item_names[0]}  {bundle.total_cost:.2f} 元")
#     export_lines.append("")
#     export_lines.append(f"总费用: {total_cost:.2f} 元  总热量: {combined.kcal:.0f} kcal")
#     st.download_button("📋 导出方案文本", "\n".join(export_lines), file_name="diet_plan.txt", mime="text/plain")

#     st.caption("💡 结果已保存 — 修改侧边栏参数不会丢失，点击「生成饮食建议」可重新规划。")

# # ══════════════════════════════════════════════════════════════════════════════
# # FOOTER
# # ══════════════════════════════════════════════════════════════════════════════

# st.divider()
# st.subheader("📚 营养标准来源")
# for title, url in SOURCE_LINKS.items():
#     st.markdown(f"- [{title}]({url})")
# st.caption("菜品营养为统一份量下的理论估算，仅用于课程项目中的相对比较，不替代医学或专业营养建议。")
from __future__ import annotations

import pandas as pd
import streamlit as st

from canteen_planner.config import ACTIVITY_FACTORS, MEAL_LABELS, PREFERENCE_CATEGORIES, SOURCE_LINKS
from canteen_planner.data_loader import load_menu
from canteen_planner.drinks import recommend_drinks
from canteen_planner.optimizer import nutrients_from_selected, optimize_plan
from canteen_planner.models import Bundle, Nutrients
from canteen_planner.nutrition import calculate_daily_targets
from canteen_planner.validation import validate_consumed_selection

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Campus Canteen Diet Planner", page_icon="🍱", layout="wide")

# ── custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* ── global ── */
    .stApp { font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; }

    /* ── metric cards ── */
    .metric-row [data-testid="stMetric"] {
        background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
        border-radius: 12px;
        padding: 12px 16px;
        border: 1px solid #e2e8f0;
    }
    .metric-highlight [data-testid="stMetric"] {
        background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
        border: 1px solid #6ee7b7;
    }

    /* ── bundle cards ── */
    .bundle-card {
        border-left: 4px solid #3b82f6;
        border-radius: 8px;
        padding: 16px 20px 12px 20px;
        margin: 10px 0;
        background: #f9fafb;
    }
    .bundle-card.primary {
        border-left-color: #10b981;
        background: linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%);
    }
    .bundle-card.over-budget {
        border-left-color: #f59e0b;
        background: #fffbeb;
    }
    .bundle-card h4 { margin-top: 0; color: #1e293b; }
    .bundle-card .shop-line { color: #64748b; font-size: 0.9em; }
    .bundle-card .price { font-weight: 700; color: #0f172a; font-size: 1.1em; }

    /* ── section headers ── */
    .section-header {
        font-size: 1.3em; font-weight: 700; color: #1e293b;
        border-bottom: 2px solid #3b82f6; padding-bottom: 6px; margin-top: 28px;
    }

    /* ── sidebar ── */
    section[data-testid="stSidebar"] { width: 380px !important; }
    section[data-testid="stSidebar"][aria-expanded="false"] { width: auto !important; }

    /* ── tabs ── */
    [data-testid="stTabs"] button { font-weight: 600; font-size: 1.02em; }

    /* ── expander ── */
    [data-testid="stExpander"] summary { font-weight: 600; }

    /* ── info/warning boxes ── */
    [data-testid="stAlert"] { border-radius: 8px; }

    /* ── button ── */
    [data-testid="baseButton-primary"] {
        background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
        font-weight: 700 !important;
        font-size: 1.05em !important;
        border-radius: 10px !important;
        padding: 0.6em 2em !important;
    }
</style>
""", unsafe_allow_html=True)

# ── cached data loader ───────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner="正在加载食堂菜单数据……")
def cached_load_menu() -> pd.DataFrame:
    return load_menu()


menu = cached_load_menu()

# ── session state init ───────────────────────────────────────────────────────
if "plan_generated" not in st.session_state:
    st.session_state.plan_generated = False
    st.session_state.meal_result = None
    st.session_state.planned_nutrients = Nutrients()
    st.session_state.total_cost = 0.0
    st.session_state.combined = Nutrients()
    st.session_state.drink_bundles = []
    st.session_state.drink_warnings = []
    st.session_state.meal_budget = None
    st.session_state.meal_only_cost = 0.0
    st.session_state.total_budget_snapshot = None
    st.session_state.consumed_snapshot = Nutrients()
    st.session_state.target_snapshot = Nutrients()
    st.session_state.remaining_meals_snapshot = []
    st.session_state.rec_counts_snapshot = {}
    st.session_state.last_total_cost = None
    st.session_state.last_combined_kcal = None


# ── helpers ──────────────────────────────────────────────────────────────────

def reserve_for_drink(total_budget: float | None) -> float | None:
    if total_budget is None or total_budget <= 0:
        return 10.0
    return min(12.0, max(3.0, total_budget * 0.2))


def bundle_rows(bundle: Bundle) -> pd.DataFrame:
    indexed = menu.set_index("id", drop=False)
    rows = indexed.loc[list(bundle.item_ids)]
    if isinstance(rows, pd.Series):
        rows = rows.to_frame().T
    return rows.reset_index(drop=True)


def render_bundle_card(bundle: Bundle, rank: int, primary: bool, title_prefix: str = "") -> None:
    title = f"{title_prefix}第{rank}名" + (" · ⭐ 建议选择" if primary else " · 备选")
    with st.container(border=True):
        st.markdown(f"#### {title}")
        col_h, col_p = st.columns([3, 1])
        with col_h:
            item_text = "  +  ".join(bundle.item_names)
            shop_text = "、".join(bundle.shops)
            location_text = "、".join(bundle.locations)
            st.markdown(f"**{item_text}**")
            st.caption(f"🏪 商家：{shop_text}　📍 地点：{location_text}")
        with col_p:
            st.metric("💰 费用", f"{bundle.total_cost:.2f} 元")

        nc1, nc2, nc3, nc4, nc5 = st.columns(5)
        nc1.metric("🔥 热量", f"{bundle.nutrients.kcal:.0f} kcal")
        nc2.metric("🥩 蛋白质", f"{bundle.nutrients.protein_g:.1f} g")
        nc3.metric("🧈 脂肪", f"{bundle.nutrients.fat_g:.1f} g")
        nc4.metric("🍚 碳水", f"{bundle.nutrients.carbs_g:.1f} g")
        nc5.metric("🍬 糖", f"{bundle.nutrients.sugar_g:.1f} g")

        if bundle.package_fee > 0 or bundle.delivery_fee > 0:
            fc1, fc2, fc3 = st.columns(3)
            fc1.caption(f"商品小计: {bundle.item_subtotal:.2f} 元")
            fc2.caption(f"打包费: {bundle.package_fee:.2f} 元")
            fc3.caption(f"配送费: {bundle.delivery_fee:.2f} 元")

        rows = bundle_rows(bundle)
        display = rows[["name", "shop", "location", "price_dinein", "price_takeout",
                         "kcal", "protein_g", "fat_g", "carbs_g", "sugar_g"]].copy()
        display.columns = ["Item", "Shop", "Location", "Dine-in 元", "Takeout 元",
                           "kcal", "Protein(g)", "Fat(g)", "Carbs(g)", "Sugar(g)"]
        st.markdown("**📋 明细表**")
        st.dataframe(display, hide_index=True, use_container_width=True)

        if bundle.explanation:
            st.info("📝 " + "；".join(bundle.explanation) + "。")

def nutrient_chart(consumed_nutrients: Nutrients, combined_nutrients: Nutrients, target: Nutrients) -> pd.DataFrame:
    return pd.DataFrame({
        "Metric": ["Energy", "Protein", "Fat", "Carbohydrate", "Fiber", "Sodium", "Sugar"],
        "已摄入 (%)": [
            consumed_nutrients.kcal / max(target.kcal, 1) * 100,
            consumed_nutrients.protein_g / max(target.protein_g, 1) * 100,
            consumed_nutrients.fat_g / max(target.fat_g, 1) * 100,
            consumed_nutrients.carbs_g / max(target.carbs_g, 1) * 100,
            consumed_nutrients.fiber_g / max(target.fiber_g, 1) * 100,
            consumed_nutrients.sodium_mg / max(target.sodium_mg, 1) * 100,
            consumed_nutrients.sugar_g / max(target.sugar_g, 1) * 100,
        ],
        "规划后 (%)": [
            combined_nutrients.kcal / max(target.kcal, 1) * 100,
            combined_nutrients.protein_g / max(target.protein_g, 1) * 100,
            combined_nutrients.fat_g / max(target.fat_g, 1) * 100,
            combined_nutrients.carbs_g / max(target.carbs_g, 1) * 100,
            combined_nutrients.fiber_g / max(target.fiber_g, 1) * 100,
            combined_nutrients.sodium_mg / max(target.sodium_mg, 1) * 100,
            combined_nutrients.sugar_g / max(target.sugar_g, 1) * 100,
        ],
    }).set_index("Metric")


def render_radar_chart(consumed: Nutrients, combined: Nutrients, target: Nutrients) -> None:
    """Plotly radar chart comparing nutrition percentages against targets."""
    try:
        import plotly.graph_objects as go  # type: ignore[import-unresolved]
    except ImportError:
        st.warning("📦 需要安装 plotly 以显示雷达图：`pip install plotly`")
        return

    categories = ["热量", "蛋白质", "脂肪", "碳水", "纤维", "钠", "糖"]

    def _pct(n: Nutrients) -> list[float]:
        return [
            min(n.kcal / max(target.kcal, 1) * 100, 150),
            min(n.protein_g / max(target.protein_g, 1) * 100, 150),
            min(n.fat_g / max(target.fat_g, 1) * 100, 150),
            min(n.carbs_g / max(target.carbs_g, 1) * 100, 150),
            min(n.fiber_g / max(target.fiber_g, 1) * 100, 150),
            min(n.sodium_mg / max(target.sodium_mg, 1) * 100, 150),
            min(n.sugar_g / max(target.sugar_g, 1) * 100, 150),
        ]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=_pct(consumed), theta=categories, fill="toself",
        name="已摄入", line=dict(color="#f59e0b", width=2),
        fillcolor="rgba(245,158,11,0.15)",
    ))
    fig.add_trace(go.Scatterpolar(
        r=_pct(combined), theta=categories, fill="toself",
        name="规划后", line=dict(color="#3b82f6", width=2),
        fillcolor="rgba(59,130,246,0.2)",
    ))
    fig.add_trace(go.Scatterpolar(
        r=[100] * 7, theta=categories, fill="none",
        name="目标 (100%)", line=dict(color="#10b981", width=2, dash="dash"),
    ))

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 150], ticksuffix="%")),
        showlegend=True, legend=dict(orientation="h", y=-0.12),
        margin=dict(l=40, r=40, t=20, b=60),
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_algorithm_trace(greedy_trace: list[dict], dp_trace: list[dict]) -> None:
    """Visualize the optimization algorithm's internal steps."""
    if not greedy_trace and not dp_trace:
        return

    with st.expander("🧾 推荐生成概览", expanded=False):
        st.markdown("#### 🔍 可选方案统计")
        if greedy_trace:
            trace_df = pd.DataFrame(greedy_trace)
            trace_display = trace_df.rename(columns={
                "meal": "餐次", "shop": "商家",
                "legal_single_shop_candidates": "合法候选数",
            })
            trace_display["餐次"] = trace_display["餐次"].map(MEAL_LABELS)
            st.dataframe(
                trace_display[["餐次", "商家", "合法候选数"]],
                hide_index=True, use_container_width=True,
            )
            st.caption(f"共 {len(greedy_trace)} 家商家参与候选生成，"
                       f"合计产出 {trace_display['合法候选数'].sum()} 个候选套餐。")

        st.markdown("#### 🧮 最终筛选统计")
        if dp_trace:
            dp_df = pd.DataFrame(dp_trace)
            dp_df["meal_label"] = dp_df["meal"].map(MEAL_LABELS)

            # ── metrics row ──
            mc1, mc2, mc3 = st.columns(3)
            total_transitions = int(dp_df["transitions"].sum())
            total_greedy = int(dp_df["greedy_candidates"].sum())
            mc1.metric("总状态转移次数", total_transitions)
            mc2.metric("候选套餐总数", total_greedy)
            mc3.metric("最终保留状态", int(dp_df["states_kept"].iloc[-1]) if not dp_df.empty else 0)

            # ── line chart: states and transitions per meal ──
            chart_data = dp_df.set_index("meal_label")[["states_kept", "transitions"]].copy()
            chart_data.columns = ["保留状态数", "转移次数"]
            st.line_chart(chart_data, use_container_width=True)

            extra_note = " 首轮预算内无合适方案，系统已自动放宽预算限制。" if any(
                not step.get("budget_enforced", True) for step in dp_trace
            ) else ""
            st.caption("系统会综合比较各餐候选方案，并保留更符合营养、预算和偏好的结果。" + extra_note)


def render_plan_comparison(
    meal_result, remaining_meals: list[str], recommendation_counts: dict,
) -> None:
    """Render a cross-meal comparison table of top-ranked bundles."""
    st.markdown('<p class="section-header">📊 方案对比总览</p>', unsafe_allow_html=True)

    rows = []
    for meal in remaining_meals:
        for rank, bundle in enumerate(
            meal_result.ranked_meal_options[meal][:recommendation_counts[meal]], start=1
        ):
            rows.append({
                "餐次": MEAL_LABELS[meal],
                "排名": rank,
                "推荐": "⭐" if rank == 1 else "",
                "内容": " + ".join(bundle.item_names),
                "商家": "、".join(bundle.shops),
                "费用": f"{bundle.total_cost:.2f} 元",
                "热量": f"{bundle.nutrients.kcal:.0f} kcal",
                "蛋白质": f"{bundle.nutrients.protein_g:.1f}g",
                "偏好覆盖": "、".join(bundle.preference_categories) if bundle.preference_categories else "—",
            })

    if rows:
        comp_df = pd.DataFrame(rows)
        st.dataframe(comp_df, hide_index=True, use_container_width=True,
                     column_config={
                         "推荐": st.column_config.TextColumn(width="small"),
                         "内容": st.column_config.TextColumn(width="large"),
                     })


def render_nutrient_bars(consumed: Nutrients, target: Nutrients) -> None:
    """Render HTML nutrient progress bars with color coding."""
    nutrients_list = [
        ("🔥 热量", consumed.kcal, target.kcal, "kcal"),
        ("🥩 蛋白质", consumed.protein_g, target.protein_g, "g"),
        ("🧈 脂肪", consumed.fat_g, target.fat_g, "g"),
        ("🍚 碳水", consumed.carbs_g, target.carbs_g, "g"),
        ("🌾 纤维", consumed.fiber_g, target.fiber_g, "g"),
        ("🧂 钠", consumed.sodium_mg, target.sodium_mg, "mg"),
        ("🍬 糖", consumed.sugar_g, target.sugar_g, "g"),
    ]
    for label, value, target_val, unit in nutrients_list:
        pct = min(value / max(target_val, 1) * 100, 150)
        if pct < 80:
            color, bg = "#ef4444", "#fef2f2"
        elif pct <= 100:
            color, bg = "#10b981", "#ecfdf5"
        else:
            color, bg = "#f59e0b", "#fffbeb"
        st.markdown(f"""
        <div style="display:flex;align-items:center;margin:4px 0;padding:6px 10px;
                    background:{bg};border-radius:6px;font-size:0.9em">
            <span style="width:90px;font-weight:600">{label}</span>
            <div style="flex:1;margin:0 10px">
                <div style="background:#e5e7eb;border-radius:3px;height:8px;width:100%">
                    <div style="width:{min(pct, 100):.0f}%;background:{color};height:8px;border-radius:3px"></div>
                </div>
            </div>
            <span style="width:130px;text-align:right;color:#64748b">
                {value:.1f} / {target_val:.0f} {unit} ({pct:.0f}%)
            </span>
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## 🍱 饮食规划")

    tab_user, tab_log, tab_settings = st.tabs(["👤 用户信息", "📝 今日记录", "⚙️ 规划设置"])

    # ── Tab 1: User Info ──
    with tab_user:
        sex = st.radio("性别", ["男", "女"], horizontal=True, key="sex")
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            age = st.number_input("年龄", 14, 100, 20, key="age")
        with col_a2:
            height = st.number_input("身高（cm）", 120.0, 220.0, 170.0, 1.0, key="height")
        weight = st.number_input("体重（kg）", 30.0, 200.0, 60.0, 0.5, key="weight")
        activity = st.selectbox("活动水平", list(ACTIVITY_FACTORS), key="activity")
        goal = st.selectbox("饮食目标", ["维持", "减脂", "增肌"], key="goal")

    # ── Tab 2: Today's Record ──
    with tab_log:
        ate_breakfast = st.checkbox("已吃早餐", value=False, key="ate_breakfast")
        ate_lunch = st.checkbox("已吃午餐", value=False, key="ate_lunch")
        ate_dinner = st.checkbox("已吃晚餐", value=False, key="ate_dinner")

    # ── Tab 3: Plan Settings ──
    with tab_settings:
        service_mode = st.radio("就餐方式", ["堂食", "外卖"], horizontal=True, key="service_mode")
        if service_mode == "堂食":
            preference = st.radio("堂食偏好", ["经济型", "便利型"], horizontal=True, key="preference")
        else:
            preference = "经济型"
            st.info("外卖按每家店计算一次打包费和配送费。")

        budget = st.number_input("剩余总预算（元，0表示不限）", 0.0, 300.0, 40.0, 1.0, key="budget")

        st.caption("各餐推荐方案数")
        rc1, rc2, rc3, rc4 = st.columns(4)
        with rc1:
            breakfast_recommendation_count = st.number_input("早餐", 1, 6, 3, 1, key="brc")
        with rc2:
            lunch_recommendation_count = st.number_input("午餐", 1, 6, 3, 1, key="lrc")
        with rc3:
            dinner_recommendation_count = st.number_input("晚餐", 1, 6, 3, 1, key="drc")
        with rc4:
            drink_recommendation_count = st.number_input("饮品", 1, 6, 3, 1, key="drkc")

        desired_categories = set(st.multiselect(
            "希望推荐的类别",
            PREFERENCE_CATEGORIES,
            default=["主食", "荤菜", "素菜"],
            help="饮品会单独推荐，不会混入早餐、午餐或晚餐。",
            key="desired_categories",
        ))
        c1, c2 = st.columns(2)
        with c1:
            avoid_fried = st.checkbox("避免油炸食品", value=False, key="avoid_fried")
        with c2:
            light_mode = st.checkbox("偏好清淡", value=False, key="light_mode")

# ── derived state (not in tabs, always computed) ──
meal_states = {"breakfast": ate_breakfast, "lunch": ate_lunch, "dinner": ate_dinner}
consumed_meals = [meal for meal, eaten in meal_states.items() if eaten]
remaining_meals = [meal for meal, eaten in meal_states.items() if not eaten]
wants_drink = "饮品" in desired_categories
meal_desired_categories = desired_categories - {"饮品"}
recommendation_counts = {
    "breakfast": int(breakfast_recommendation_count),
    "lunch": int(lunch_recommendation_count),
    "dinner": int(dinner_recommendation_count),
}

# ══════════════════════════════════════════════════════════════════════════════
# MAIN AREA
# ══════════════════════════════════════════════════════════════════════════════

st.title("🍱 校园食堂饮食规划系统")
st.caption("根据个人信息、今日已吃内容、预算和食堂菜单，给出正餐与饮品建议。")

# ── compute targets ──
result_target = calculate_daily_targets(sex, int(age), float(height), float(weight), activity, goal)

# ── consumed food selection ──
selections: dict[str, float] = {}

if consumed_meals:
    st.markdown('<p class="section-header">📝 记录已经吃过的食物</p>', unsafe_allow_html=True)
    for meal in consumed_meals:
        availability = {"breakfast": "available_breakfast", "lunch": "available_lunch", "dinner": "available_dinner"}[meal]
        options_df = menu[menu[availability].eq(1) & ~menu["item_role"].eq("auto_free")].copy()
        # ── food search ──
        search_term = st.text_input(
            f"🔍 搜索{MEAL_LABELS[meal]}食物（按名称/商家/地点）",
            key=f"search_{meal}", placeholder="输入关键词过滤……",
        )
        if search_term:
            term = search_term.lower()
            options_df = options_df[
                options_df["name"].str.lower().str.contains(term, na=False)
                | options_df["shop"].str.lower().str.contains(term, na=False)
                | options_df["location"].str.lower().str.contains(term, na=False)
            ]
            if options_df.empty:
                st.caption(f"没有匹配「{search_term}」的食物，请尝试其他关键词。")
        labels = {row["id"]: f'{row["name"]}｜{row["shop"]}｜{row["location"]}' for _, row in options_df.iterrows()}
        selected = st.multiselect(
            f"{MEAL_LABELS[meal]}吃了什么？（{len(options_df)} 项）",
            options_df["id"].tolist(),
            format_func=lambda item_id, mapping=labels: mapping.get(item_id, item_id),
            key=f"selected_{meal}",
        )
        for item_id in selected:
            selections[item_id] = float(st.number_input(
                f"{labels[item_id]}：份数", 0.25, 5.0, 1.0, 0.25,
                key=f"servings_{meal}_{item_id}",
            ))

consumed = nutrients_from_selected(menu, selections)
if selections:
    for warning in validate_consumed_selection(menu[menu["id"].isin(selections)]):
        st.warning(warning)

# ── nutrition dashboard ──
st.markdown('<p class="section-header">📈 营养概览</p>', unsafe_allow_html=True)
bmi_col, bars_col = st.columns([1, 2])
with bmi_col:
    bmi_val = result_target.bmi
    bmi_color = "#10b981" if 18.5 <= bmi_val < 24 else ("#f59e0b" if bmi_val < 28 else "#ef4444")
    st.markdown(f"""
    <div style="text-align:center;padding:16px 8px;background:linear-gradient(135deg,#f8fafc,#e2e8f0);
                border-radius:12px;border:1px solid #e2e8f0">
        <div style="font-size:0.85em;color:#64748b;margin-bottom:4px">BMI 指数</div>
        <div style="font-size:2.4em;font-weight:800;color:{bmi_color}">{bmi_val:.1f}</div>
        <div style="font-size:0.9em;color:{bmi_color};font-weight:600">{result_target.bmi_label}</div>
        <div style="font-size:0.75em;color:#94a3b8;margin-top:4px">
            目标 {result_target.nutrients.kcal:.0f} kcal · 蛋白质 {result_target.nutrients.protein_g:.0f}g
        </div>
    </div>
    """, unsafe_allow_html=True)
with bars_col:
    if consumed.kcal > 0:
        render_nutrient_bars(consumed, result_target.nutrients)
    else:
        st.info("👆 在侧边栏记录已吃食物后，这里会显示营养摄入进度。")

with st.expander("📖 查看基础规则"):
    st.write("早餐仅从早餐开放窗口推荐；午餐和晚餐从正餐开放窗口推荐。")
    st.write("加料、免费配菜和必选米饭不能单独购买。")
    st.write("堂食符合条件时会显示免费例汤，免费例汤营养价值较低。")
    st.write("饮品和冰淇淋单独推荐，不会混入正餐套餐。")

# ── empty-state guide ──
if not st.session_state.plan_generated:
    st.info("👆 在侧边栏填写个人信息和规划设置，然后点击下方按钮即可获得个性化饮食方案。")

# ══════════════════════════════════════════════════════════════════════════════
# GENERATE BUTTON
# ══════════════════════════════════════════════════════════════════════════════

if st.button("🚀 生成饮食建议", type="primary", use_container_width=True):
    planned_nutrients = Nutrients()
    total_cost = 0.0
    meal_only_cost = 0.0
    meal_result = None
    drink_bundles = []
    drink_warnings = []
    total_budget = None if budget <= 0 else float(budget)
    meal_budget = total_budget
    if wants_drink and total_budget is not None and remaining_meals:
        meal_budget = max(0.0, total_budget - float(reserve_for_drink(total_budget) or 0.0))

    if remaining_meals:
        try:
            with st.status("🍳 正在生成饮食建议……", expanded=True) as status_ctx:
                def on_progress(msg: str) -> None:
                    status_ctx.write(msg)

                meal_result = optimize_plan(
                    menu=menu,
                    daily_target=result_target.nutrients,
                    consumed=consumed,
                    remaining_meals=remaining_meals,
                    service_mode=service_mode,
                    preference=preference,
                    budget=meal_budget,
                    avoid_fried=avoid_fried,
                    desired_categories=desired_categories,
                    light_mode=light_mode,
                    recommendation_count=max(recommendation_counts[meal] for meal in remaining_meals),
                    progress_callback=on_progress,
                )
                status_ctx.update(label="✅ 正餐规划完成！", state="complete")
        except ValueError as exc:
            st.error(str(exc))
            st.session_state.plan_generated = False
            st.stop()

        planned_nutrients = meal_result.planned
        total_cost = meal_result.total_cost
        meal_only_cost = meal_result.total_cost
    else:
        meal_result = None
        st.info("三餐都已记录，本次不再规划正餐。")

    if wants_drink:
        current_after_meals = consumed + planned_nutrients
        budget_left = None if total_budget is None else max(total_budget - total_cost, 0.0)
        with st.status("🥤 正在分析饮品与冰淇淋建议……", expanded=True) as drink_status:
            drink_bundles, drink_warnings = recommend_drinks(
                menu=menu,
                target=result_target.nutrients,
                current=current_after_meals,
                service_mode=service_mode,
                budget_left=budget_left,
                count=int(drink_recommendation_count),
                remaining_meals=remaining_meals,
                consumed_meals=consumed_meals,
                planned_cost=meal_only_cost,
                full_budget=total_budget,
            )
            drink_status.update(label=f"✅ 饮品分析完成！共 {len(drink_bundles)} 个推荐", state="complete")
        if drink_bundles:
            planned_nutrients = planned_nutrients + drink_bundles[0].nutrients
            total_cost += drink_bundles[0].total_cost

    combined = consumed + planned_nutrients
    if st.session_state.total_cost and st.session_state.total_cost > 0:
        st.session_state.last_total_cost = st.session_state.total_cost
        st.session_state.last_combined_kcal = st.session_state.combined.kcal
    st.session_state.plan_generated = True
    st.session_state.meal_result = meal_result
    st.session_state.planned_nutrients = planned_nutrients
    st.session_state.total_cost = total_cost
    st.session_state.combined = combined
    st.session_state.meal_budget = meal_budget
    st.session_state.meal_only_cost = meal_only_cost
    st.session_state.total_budget_snapshot = total_budget
    st.session_state.drink_bundles = drink_bundles
    st.session_state.drink_warnings = drink_warnings
    st.session_state.consumed_snapshot = consumed
    st.session_state.target_snapshot = result_target.nutrients
    st.session_state.remaining_meals_snapshot = remaining_meals
    st.session_state.rec_counts_snapshot = recommendation_counts

# ══════════════════════════════════════════════════════════════════════════════
# RESULTS (persisted via session_state)
# ══════════════════════════════════════════════════════════════════════════════

if st.session_state.plan_generated:
    meal_result = st.session_state.meal_result
    planned_nutrients = st.session_state.planned_nutrients
    total_cost = st.session_state.total_cost
    combined = st.session_state.combined
    meal_budget = st.session_state.meal_budget
    meal_only_cost = st.session_state.meal_only_cost
    total_budget_snapshot = st.session_state.total_budget_snapshot
    drink_bundles = st.session_state.drink_bundles
    drink_warnings = st.session_state.drink_warnings
    consumed_snap = st.session_state.consumed_snapshot
    target_snap = st.session_state.target_snapshot
    stored_remaining = st.session_state.remaining_meals_snapshot
    stored_recs = st.session_state.rec_counts_snapshot

    if st.session_state.last_total_cost is not None:
        delta_cost = total_cost - st.session_state.last_total_cost
        delta_kcal = combined.kcal - st.session_state.last_combined_kcal
        st.caption(
            f"📊 与上次对比：费用 {delta_cost:+.2f} 元　｜　"
            f"热量 {delta_kcal:+.0f} kcal"
        )

    st.markdown('<p class="section-header">🍽️ 规划结果</p>', unsafe_allow_html=True)
    top = st.columns(5)
    top[0].metric("正餐费用", f"{meal_only_cost:.2f} 元")
    top[1].metric("剩余总预算", "不限" if total_budget_snapshot is None else f"{total_budget_snapshot:.2f} 元")
    utilization = 0 if not total_budget_snapshot else total_cost / total_budget_snapshot * 100
    top[2].metric("总预算使用率", "—" if not total_budget_snapshot else f"{utilization:.1f}%")
    top[3].metric("规划餐次", 0 if meal_result is None else len(meal_result.bundles))
    top[4].metric("规划后热量", f"{combined.kcal:.0f} kcal")

    if meal_result is not None:
        render_algorithm_trace(meal_result.greedy_trace, meal_result.dp_trace)
        render_plan_comparison(meal_result, stored_remaining, stored_recs)

        st.markdown('<p class="section-header">🍱 正餐建议</p>', unsafe_allow_html=True)
        for meal in stored_remaining:
            st.subheader(MEAL_LABELS[meal])
            for rank, bundle in enumerate(
                meal_result.ranked_meal_options[meal][:stored_recs[meal]], start=1
            ):
                render_bundle_card(bundle, rank, primary=(rank == 1))

        for warning in meal_result.warnings:
            st.warning(warning)
    else:
        st.info("三餐均已记录，本次只根据今日已摄入情况推荐额外饮品或冰淇淋。")

    if drink_bundles:
        st.markdown('<p class="section-header">🥤 饮品与冰淇淋建议</p>', unsafe_allow_html=True)
        for rank, bundle in enumerate(drink_bundles, start=1):
            render_bundle_card(bundle, rank, primary=(rank == 1), title_prefix="饮品")
    elif wants_drink:
        st.warning("当前预算或糖分限制下，没有找到合适的额外饮品。")

    for warning in drink_warnings:
        st.warning(warning)

    st.markdown('<p class="section-header">📊 营养完成度</p>', unsafe_allow_html=True)
    chart_col, radar_col = st.columns([1, 1])
    with chart_col:
        st.markdown("##### 柱状图对比")
        st.bar_chart(nutrient_chart(consumed_snap, combined, target_snap))
    with radar_col:
        st.markdown("##### 雷达图")
        render_radar_chart(consumed_snap, combined, target_snap)

    st.metric("💰 本次建议总费用", f"{total_cost:.2f} 元")

    export_lines = ["校园食堂饮食规划方案", "=" * 30, ""]
    if meal_result is not None:
        for meal in stored_remaining:
            export_lines.append(f"【{MEAL_LABELS[meal]}】")
            for rank, bundle in enumerate(meal_result.ranked_meal_options[meal][:stored_recs[meal]], start=1):
                star = "⭐" if rank == 1 else "  "
                export_lines.append(f"  {star} 第{rank}名: {' + '.join(bundle.item_names)}")
                export_lines.append(f"      商家: {'、'.join(bundle.shops)}  费用: {bundle.total_cost:.2f} 元")
                export_lines.append(f"      热量: {bundle.nutrients.kcal:.0f} kcal  蛋白质: {bundle.nutrients.protein_g:.1f}g")
    if drink_bundles:
        export_lines.append("")
        export_lines.append("【饮品】")
        for rank, bundle in enumerate(drink_bundles, start=1):
            export_lines.append(f"  第{rank}名: {bundle.item_names[0]}  {bundle.total_cost:.2f} 元")
    export_lines.append("")
    export_lines.append(f"总费用: {total_cost:.2f} 元  总热量: {combined.kcal:.0f} kcal")
    st.download_button("📋 导出方案文本", "\n".join(export_lines), file_name="diet_plan.txt", mime="text/plain")

    st.caption("💡 结果已保存 — 修改侧边栏参数不会丢失，点击「生成饮食建议」可重新规划。")

# ══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════════════════════

st.divider()
st.subheader("📚 营养标准来源")
for title, url in SOURCE_LINKS.items():
    st.markdown(f"- [{title}]({url})")
st.caption("菜品营养为统一份量下的理论估算，仅用于课程项目中的相对比较，不替代医学或专业营养建议。")
