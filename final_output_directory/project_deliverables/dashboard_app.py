#!/usr/bin/env python3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

BASE = Path("./chennai_spending_project/outputs")
MASTER = BASE / "chennai_spending_master.csv"

st.set_page_config(page_title="Chennai Spending Dashboard", layout="wide")
st.title("Government Spending in Chennai")

df = pd.read_csv(MASTER, low_memory=False)
df["amount_crore"] = pd.to_numeric(df["amount_crore"], errors="coerce")
df = df.dropna(subset=["amount_crore"])

levels = sorted(df["gov_level"].dropna().unique())
years = sorted(df["fiscal_year"].dropna().unique())
sectors = sorted(df["sector"].dropna().unique())

col1, col2, col3 = st.columns(3)
sel_levels = col1.multiselect("Gov level", levels, default=levels)
sel_years = col2.multiselect("Fiscal year", years, default=years)
sel_sectors = col3.multiselect("Sector", sectors, default=sectors)

f = df[
    df["gov_level"].isin(sel_levels)
    & df["fiscal_year"].isin(sel_years)
    & df["sector"].isin(sel_sectors)
]

st.metric("Total amount (crore)", f"{f['amount_crore'].sum():,.2f}")

yearly = f.groupby(["fiscal_year", "gov_level"], as_index=False)["amount_crore"].sum()
fig1 = px.line(yearly, x="fiscal_year", y="amount_crore", color="gov_level", markers=True, title="Yearly trend by government level")
st.plotly_chart(fig1, use_container_width=True)

sector_tot = f.groupby(["sector", "gov_level"], as_index=False)["amount_crore"].sum()
fig2 = px.bar(sector_tot, x="sector", y="amount_crore", color="gov_level", barmode="group", title="Sector allocations")
st.plotly_chart(fig2, use_container_width=True)

st.subheader("Sample records")
st.dataframe(f[["gov_level", "fiscal_year", "sector", "amount_crore", "row_text"]].head(200), use_container_width=True)
