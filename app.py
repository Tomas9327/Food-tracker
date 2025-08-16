
import streamlit as st
import pandas as pd
import json
from datetime import date, datetime, timedelta
from pathlib import Path
import matplotlib.pyplot as plt

FOODS_CSV = "foods.csv"
LOG_CSV = "log.csv"
GOALS_JSON = "goals.json"

# ------------- Data loading/saving -------------
@st.cache_data
def load_foods():
    path = Path(FOODS_CSV)
    if not path.exists():
        # seed with minimal defaults if not found
        seed = pd.DataFrame([
            ("Chicken breast (raw)", 100, "g", 165, 31.0, 3.6, 1.0),
            ("Rolled oats (dry)",    100, "g", 379, 13.0, 7.0, 1.2),
        ], columns=["name","base_amount","unit","calories","protein_g","fat_g","sat_fat_g"])
        seed.to_csv(path, index=False)
    return pd.read_csv(path)

def save_foods(df):
    df.to_csv(FOODS_CSV, index=False)
    load_foods.clear()  # invalidate cache

def load_log():
    path = Path(LOG_CSV)
    if not path.exists():
        cols = ["date","food","quantity","unit","base_amount","calories","protein_g","fat_g","sat_fat_g"]
        pd.DataFrame(columns=cols).to_csv(path, index=False)
    return pd.read_csv(path, parse_dates=["date"])

def save_log(df):
    df.to_csv(LOG_CSV, index=False)

def load_goals():
    path = Path(GOALS_JSON)
    if not path.exists():
        goals = {"calories": 1800, "protein_g": 120, "sat_fat_g": 20}
        path.write_text(json.dumps(goals, indent=2))
        return goals
    return json.loads(path.read_text())

def save_goals(goals):
    Path(GOALS_JSON).write_text(json.dumps(goals, indent=2))

# ------------- Helper computations -------------
def compute_nutrients(row, qty):
    """qty in the same unit as food base (g/ml/unit)."""
    factor = qty / row["base_amount"]
    return {
        "calories": row["calories"] * factor,
        "protein_g": row["protein_g"] * factor,
        "fat_g": row["fat_g"] * factor,
        "sat_fat_g": row["sat_fat_g"] * factor,
    }

def daily_summary(log_df, day):
    day_df = log_df[log_df["date"] == pd.to_datetime(day)]
    totals = day_df[["calories","protein_g","fat_g","sat_fat_g"]].sum()
    return day_df, totals

def weekly_summary(log_df, end_day):
    start = pd.to_datetime(end_day) - pd.Timedelta(days=6)
    mask = (log_df["date"] >= start) & (log_df["date"] <= pd.to_datetime(end_day))
    week = log_df[mask].copy()
    by_day = week.groupby(week["date"].dt.date)[["calories","protein_g","sat_fat_g"]].sum().reset_index()
    return week, by_day

# ------------- UI -------------
st.set_page_config(page_title="Food Tracker", page_icon="🍽️", layout="wide")
st.title("🍽️ Food Tracker — Calories • Protein • Saturated Fat")

foods = load_foods()
log = load_log()
goals = load_goals()

with st.sidebar:
    st.header("Goals")
    cal_goal = st.number_input("Daily calories goal", min_value=500, max_value=5000, value=int(goals["calories"]), step=50)
    protein_goal = st.number_input("Daily protein goal (g)", min_value=20, max_value=400, value=int(goals["protein_g"]), step=5)
    sat_fat_limit = st.number_input("Daily saturated fat limit (g)", min_value=5, max_value=80, value=int(goals["sat_fat_g"]), step=1)
    if st.button("Save goals"):
        goals = {"calories": cal_goal, "protein_g": protein_goal, "sat_fat_g": sat_fat_limit}
        save_goals(goals)
        st.success("Goals saved.")

tabs = st.tabs(["Log Food", "Today", "This Week", "Manage Foods", "Export/Import"])

# ---- Log Food ----
with tabs[0]:
    st.subheader("Log Food")
    log_date = st.date_input("Date", value=date.today())
    # Food selector
    food_names = foods["name"].tolist()
    food_choice = st.selectbox("Food", food_names)
    food_row = foods[foods["name"] == food_choice].iloc[0]
    st.write(f"Nutrition is per **{int(food_row['base_amount'])}{food_row['unit']}**.")
    qty = st.number_input(f"Quantity ({food_row['unit']})", min_value=1.0, value=float(food_row["base_amount"]), step=1.0)
    if st.button("Add to log"):
        n = compute_nutrients(food_row, qty)
        new = {
            "date": pd.to_datetime(log_date),
            "food": food_choice,
            "quantity": qty,
            "unit": food_row["unit"],
            "base_amount": food_row["base_amount"],
            **n
        }
        log = pd.concat([log, pd.DataFrame([new])], ignore_index=True)
        save_log(log)
        st.success(f"Added {qty}{food_row['unit']} of {food_choice} to {log_date}.")

    if not log.empty:
        st.write("Recent entries")
        recent = log.sort_values("date", ascending=False).head(20)
        st.dataframe(recent)

# ---- Today ----
with tabs[1]:
    st.subheader("Today’s Summary")
    today = date.today()
    day_df, totals = daily_summary(log, today)
    st.write(f"Date: **{today}**")
    st.metric("Calories", f"{int(totals.get('calories',0))} / {cal_goal} kcal")
    st.progress(min(totals.get('calories',0)/cal_goal, 1.0))
    st.metric("Protein", f"{int(totals.get('protein_g',0))} / {protein_goal} g")
    st.progress(min(totals.get('protein_g',0)/protein_goal, 1.0))
    st.metric("Saturated Fat", f"{round(totals.get('sat_fat_g',0),1)} / {sat_fat_limit} g")
    st.progress(min(totals.get('sat_fat_g',0)/sat_fat_limit, 1.0))

    if not day_df.empty:
        st.write("Today's log")
        st.dataframe(day_df)

# ---- This Week ----
with tabs[2]:
    st.subheader("This Week (last 7 days incl. today)")
    week_df, by_day = weekly_summary(log, date.today())
    if not by_day.empty:
        st.dataframe(by_day)
        # Calories chart
        fig1, ax1 = plt.subplots()
        ax1.plot(by_day["date"], by_day["calories"])
        ax1.set_title("Daily Calories (7 days)")
        ax1.set_xlabel("Date")
        ax1.set_ylabel("Calories")
        st.pyplot(fig1)
        # Sat fat chart
        fig2, ax2 = plt.subplots()
        ax2.plot(by_day["date"], by_day["sat_fat_g"])
        ax2.set_title("Daily Saturated Fat (g)")
        ax2.set_xlabel("Date")
        ax2.set_ylabel("Sat Fat (g)")
        st.pyplot(fig2)
    else:
        st.info("No entries this week yet.")

# ---- Manage Foods ----
with tabs[3]:
    st.subheader("Food Database")
    st.write("Add a new food or edit existing values. Nutrition should correspond to the base amount (e.g., per 100g, per 100ml, or per 1 unit).")
    with st.expander("Add new food"):
        name = st.text_input("Name")
        base_amount = st.number_input("Base amount", min_value=1.0, value=100.0, step=1.0)
        unit = st.selectbox("Unit", ["g","ml","unit"])
        calories = st.number_input("Calories (per base amount)", min_value=0.0, value=0.0, step=1.0)
        protein = st.number_input("Protein g (per base amount)", min_value=0.0, value=0.0, step=0.1)
        fat = st.number_input("Fat g (per base amount)", min_value=0.0, value=0.0, step=0.1)
        sat_fat = st.number_input("Saturated fat g (per base amount)", min_value=0.0, value=0.0, step=0.1)
        if st.button("Add food"):
            if name.strip():
                new_row = pd.DataFrame([{
                    "name": name.strip(),
                    "base_amount": base_amount,
                    "unit": unit,
                    "calories": calories,
                    "protein_g": protein,
                    "fat_g": fat,
                    "sat_fat_g": sat_fat
                }])
                foods_updated = pd.concat([foods, new_row], ignore_index=True)
                save_foods(foods_updated)
                st.success(f"Added '{name}'. Reload the page to see it in the selector.")
            else:
                st.warning("Please enter a name.")

    st.write("Current foods")
    st.dataframe(foods)

# ---- Export/Import ----
with tabs[4]:
    st.subheader("Export / Import")
    st.write("Download your current **foods** and **log**. You can edit them in a spreadsheet and re-upload.")
    st.download_button("Download foods.csv", data=foods.to_csv(index=False), file_name="foods.csv", mime="text/csv")
    st.download_button("Download log.csv", data=log.to_csv(index=False), file_name="log.csv", mime="text/csv")

    st.write("Upload edited files to replace current data.")
    uploaded_foods = st.file_uploader("Upload foods.csv", type=["csv"])
    if uploaded_foods is not None:
        new_foods = pd.read_csv(uploaded_foods)
        save_foods(new_foods)
        st.success("foods.csv replaced. Please refresh the page.")
    uploaded_log = st.file_uploader("Upload log.csv", type=["csv"])
    if uploaded_log is not None:
        new_log = pd.read_csv(uploaded_log, parse_dates=["date"])
        save_log(new_log)
        st.success("log.csv replaced. Please refresh the page.")
