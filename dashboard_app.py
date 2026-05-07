#!/usr/bin/env python3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

BASE = Path("./chennai_spending_project/outputs")
MASTER = BASE / "chennai_spending_master.csv"
AI_INSIGHTS = BASE / "ai_insights.json"

st.set_page_config(
    page_title="Chennai Government Spending Intelligence",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.title("Chennai Government Spending Intelligence Dashboard")
st.caption("Union + Tamil Nadu State + Chennai Corporation | Amounts in crore")


@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    frame = pd.read_csv(MASTER, low_memory=False)
    frame["amount_crore"] = pd.to_numeric(frame["amount_crore"], errors="coerce")
    frame = frame.dropna(subset=["amount_crore"]).copy()
    frame["fiscal_year"] = frame["fiscal_year"].astype(str)
    frame["gov_level"] = frame["gov_level"].astype(str)
    frame["sector"] = frame["sector"].fillna("other").astype(str)
    frame["row_text"] = frame["row_text"].fillna("").astype(str)
    return frame


df = load_data()
levels = sorted(df["gov_level"].dropna().unique().tolist())
years = sorted(df["fiscal_year"].dropna().unique().tolist())
sectors = sorted(df["sector"].dropna().unique().tolist())

# Sidebar controls
st.sidebar.header("Filters")
sel_levels = st.sidebar.multiselect("Government level", levels, default=levels)
sel_years = st.sidebar.multiselect("Fiscal year", years, default=years)
sel_sectors = st.sidebar.multiselect("Sector", sectors, default=sectors)
min_amount, max_amount = float(df["amount_crore"].min()), float(df["amount_crore"].max())
amount_range = st.sidebar.slider(
    "Amount range (crore)",
    min_value=min_amount,
    max_value=max_amount,
    value=(min_amount, max_amount),
)
search_text = st.sidebar.text_input("Row text contains (optional)")

f = df[
    df["gov_level"].isin(sel_levels)
    & df["fiscal_year"].isin(sel_years)
    & df["sector"].isin(sel_sectors)
    & (df["amount_crore"] >= amount_range[0])
    & (df["amount_crore"] <= amount_range[1])
].copy()
if search_text.strip():
    f = f[f["row_text"].str.contains(search_text.strip(), case=False, na=False)]

if f.empty:
    st.warning("No data matches the selected filters.")
    st.stop()

# KPI Row
k1, k2, k3, k4 = st.columns(4)
total_amount = f["amount_crore"].sum()
k1.metric("Total Spend (crore)", f"{total_amount:,.2f}")
k2.metric("Rows", f"{len(f):,}")
k3.metric("Distinct Sectors", f"{f['sector'].nunique():,}")
k4.metric("Gov Levels", ", ".join(sorted(f["gov_level"].unique())))

tab1, tab2, tab3, tab4 = st.tabs(
    ["Trends", "Sector Mix", "Deep Dive Table", "AI Insights"]
)

with tab1:
    yearly = (
        f.groupby(["fiscal_year", "gov_level"], as_index=False)["amount_crore"]
        .sum()
        .sort_values(["fiscal_year", "gov_level"])
    )
    fig1 = px.line(
        yearly,
        x="fiscal_year",
        y="amount_crore",
        color="gov_level",
        markers=True,
        title="Yearly Spending Trend by Government Level",
    )
    fig1.update_layout(legend_title_text="Government Level")
    st.plotly_chart(fig1, use_container_width=True)

    yoy = yearly.sort_values(["gov_level", "fiscal_year"]).copy()
    yoy["yoy_pct"] = yoy.groupby("gov_level")["amount_crore"].pct_change() * 100.0
    fig_yoy = px.bar(
        yoy.dropna(subset=["yoy_pct"]),
        x="fiscal_year",
        y="yoy_pct",
        color="gov_level",
        barmode="group",
        title="YoY Growth (%) by Government Level",
    )
    st.plotly_chart(fig_yoy, use_container_width=True)

with tab2:
    sector_tot = (
        f.groupby(["sector", "gov_level"], as_index=False)["amount_crore"]
        .sum()
        .sort_values("amount_crore", ascending=False)
    )
    fig2 = px.bar(
        sector_tot,
        x="sector",
        y="amount_crore",
        color="gov_level",
        barmode="group",
        title="Sector Allocation by Government Level",
    )
    fig2.update_xaxes(tickangle=45)
    st.plotly_chart(fig2, use_container_width=True)

    sun = (
        f.groupby(["gov_level", "sector"], as_index=False)["amount_crore"]
        .sum()
        .sort_values("amount_crore", ascending=False)
    )
    fig3 = px.sunburst(
        sun,
        path=["gov_level", "sector"],
        values="amount_crore",
        title="Spending Composition (Level -> Sector)",
    )
    st.plotly_chart(fig3, use_container_width=True)

with tab3:
    st.subheader("Detailed Records")
    view_cols = ["gov_level", "fiscal_year", "sector", "amount_crore", "row_text"]
    st.dataframe(
        f[view_cols].sort_values("amount_crore", ascending=False).head(1000),
        use_container_width=True,
        height=480,
    )
    csv_bytes = f[view_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Filtered Data (CSV)",
        data=csv_bytes,
        file_name="filtered_chennai_spending.csv",
        mime="text/csv",
    )

with tab4:
    st.subheader("AI-Driven Insight Snapshot")
    if AI_INSIGHTS.exists():
        try:
            ai = pd.read_json(AI_INSIGHTS, typ="series")
            st.json(ai.to_dict())
        except Exception:
            st.info("`ai_insights.json` is present but could not be rendered as JSON.")
    else:
        st.info("AI insights file not found.")

    # Lightweight anomaly view from current filter
    sy = f.groupby(["gov_level", "sector", "fiscal_year"], as_index=False)["amount_crore"].sum()
    sy["zscore"] = sy.groupby(["gov_level", "sector"])["amount_crore"].transform(
        lambda s: (s - s.mean()) / (s.std(ddof=0) if s.std(ddof=0) else 0.0)
    )
    anom = sy[sy["zscore"].abs() >= 1.8].sort_values("zscore", ascending=False)
    st.markdown("**Anomaly Candidates (|z| >= 1.8)**")
    st.dataframe(anom.head(200), use_container_width=True, height=320)
