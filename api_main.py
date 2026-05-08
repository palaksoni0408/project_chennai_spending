#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Optional
import re
import json

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

BASE = Path(__file__).parent / "outputs"
MASTER = BASE / "chennai_spending_master.csv"
SEMANTIC_CACHE = BASE / "semantic_descriptions.json"

app = FastAPI(title="Chennai Spending API", version="1.0.0")
ALLOWED_ORIGINS = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://project-chennai-spending.onrender.com",
    "https://chennai-spending.onrender.com",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static frontend files
STATIC_DIR = Path(__file__).parent
app.mount("/assets", StaticFiles(directory=STATIC_DIR, html=True), name="assets")

@app.get("/", include_in_schema=False)
def root():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "API is running. Open /index.html or serve the frontend separately."}

_DF: Optional[pd.DataFrame] = None
_SEM_MAP: Optional[dict[str, str]] = None


def clean_description(text: str) -> str:
    t = str(text or "")
    # Remove long numeric blobs and parenthetical OCR artifacts.
    t = re.sub(r"\(?\d{6,}(?:\.\d+)?\)?", " ", t)
    # Remove Indian-style currency strings like 31,89,37,68,738.
    t = re.sub(r"\b\d{1,3}(?:,\d{2,3}){2,}(?:\.\d+)?\b", " ", t)
    # Remove decimal fragments often produced by OCR around totals.
    t = re.sub(r"\b\d+\.\d+\b", " ", t)
    # Remove very short numeric fragments.
    t = re.sub(r"\b\d{1,3}\b", " ", t)
    t = re.sub(r"[_|]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip(" -,:;[]()")

    # Keep readable ASCII-like text for stable dashboard display.
    t = re.sub(r"[^\x20-\x7E]", " ", t)
    t = re.sub(r"\s+", " ", t).strip(" -,:;[]()")

    # Standardize and reduce noisy headers.
    upper = t.upper()
    noisy_prefixes = [
        "TOTAL",
        "A TOTAL",
        "TOTAL ASSETS",
        "TOTAL LIABILITIES",
        "TOTAL INCOME",
    ]
    for p in noisy_prefixes:
        if upper.startswith(p):
            t = t[len(p):].strip(" -,:;[]()")
            break

    # If nothing meaningful remains, mark as unavailable.
    # Drop generic total-like leftovers.
    if re.fullmatch(r"(?i)(total|assets|liabilities|income|account|a b|b a|ab)", t):
        return "N/A"
    if len(t) < 4 or re.fullmatch(r"[A-Za-z]?", t):
        return "N/A"
    return t


def load_semantic_map() -> dict[str, str]:
    global _SEM_MAP
    if _SEM_MAP is None:
        if SEMANTIC_CACHE.exists():
            try:
                data = json.loads(SEMANTIC_CACHE.read_text())
                _SEM_MAP = {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
            except Exception:
                _SEM_MAP = {}
        else:
            _SEM_MAP = {}
    return _SEM_MAP


def load_df() -> pd.DataFrame:
    global _DF
    if _DF is None:
        df = pd.read_csv(MASTER, low_memory=False)
        df["amount_crore"] = pd.to_numeric(df["amount_crore"], errors="coerce")
        df = df.dropna(subset=["amount_crore"]).copy()
        df["fiscal_year"] = df["fiscal_year"].astype(str)
        df["gov_level"] = df["gov_level"].astype(str)
        df["sector"] = df["sector"].fillna("other").astype(str)
        df["row_text"] = df["row_text"].fillna("").astype(str)
        df["clean_description"] = df["row_text"].map(clean_description)
        sem = load_semantic_map()
        df["semantic_description"] = df["row_text"].map(lambda x: sem.get(x, ""))
        df["semantic_description"] = df["semantic_description"].fillna("")
        df["display_description"] = df["semantic_description"]
        df.loc[df["display_description"].str.strip() == "", "display_description"] = df["clean_description"]
        # Mark OCR-concatenated outliers as non-sane for visualization/ranking.
        sane_limit = (
            df.groupby("gov_level")["amount_crore"]
            .transform(lambda s: max(float(s.quantile(0.995)), 1_000_000.0))
        )
        df["amount_crore_sane"] = df["amount_crore"] <= sane_limit
        df["amount_crore_viz"] = df["amount_crore"].where(df["amount_crore_sane"], pd.NA)
        _DF = df
    return _DF


def apply_filters(
    df: pd.DataFrame,
    gov_levels: Optional[list[str]],
    fiscal_years: Optional[list[str]],
    sectors: Optional[list[str]],
    q: str,
) -> pd.DataFrame:
    out = df
    if gov_levels:
        out = out[out["gov_level"].isin(gov_levels)]
    if fiscal_years:
        out = out[out["fiscal_year"].isin(fiscal_years)]
    if sectors:
        out = out[out["sector"].isin(sectors)]
    if q:
        out = out[
            out["row_text"].str.contains(q, case=False, na=False)
            | out["clean_description"].str.contains(q, case=False, na=False)
        ]
    return out


def aggregate_timeseries(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build yearly timeseries by summing amount_crore_viz per fiscal_year and gov_level.
    """
    rows: list[dict] = []
    for (fiscal_year, gov_level), g in df.groupby(["fiscal_year", "gov_level"]):
        rows.append(
            {
                "fiscal_year": fiscal_year,
                "gov_level": gov_level,
                "amount_crore": float(g["amount_crore_viz"].sum()) if not g.empty else 0.0,
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["fiscal_year", "gov_level"])


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/filters")
def filters() -> dict:
    df = load_df()
    return {
        "gov_levels": sorted(df["gov_level"].unique().tolist()),
        "fiscal_years": sorted(df["fiscal_year"].unique().tolist()),
        "sectors": sorted(df["sector"].unique().tolist()),
    }


@app.get("/kpis")
def kpis(
    gov_levels: Optional[list[str]] = Query(default=None),
    fiscal_years: Optional[list[str]] = Query(default=None),
    sectors: Optional[list[str]] = Query(default=None),
    q: str = "",
) -> dict:
    df = apply_filters(load_df(), gov_levels, fiscal_years, sectors, q)
    viz_df = df.dropna(subset=["amount_crore_viz"])
    return {
        "rows": int(len(df)),
        "total_amount_crore": float(df["amount_crore"].sum()),
        "viz_rows": int(len(viz_df)),
        "viz_total_amount_crore": float(viz_df["amount_crore_viz"].sum()) if len(viz_df) else 0.0,
        "distinct_sectors": int(df["sector"].nunique()),
        "distinct_levels": int(df["gov_level"].nunique()),
    }


@app.get("/timeseries")
def timeseries(
    gov_levels: Optional[list[str]] = Query(default=None),
    fiscal_years: Optional[list[str]] = Query(default=None),
    sectors: Optional[list[str]] = Query(default=None),
    q: str = "",
) -> list[dict]:
    df = apply_filters(load_df(), gov_levels, fiscal_years, sectors, q)
    df = df.dropna(subset=["amount_crore_viz"])
    g = aggregate_timeseries(df)
    return g.to_dict(orient="records")


@app.get("/sector-mix")
def sector_mix(
    gov_levels: Optional[list[str]] = Query(default=None),
    fiscal_years: Optional[list[str]] = Query(default=None),
    sectors: Optional[list[str]] = Query(default=None),
    q: str = "",
) -> list[dict]:
    df = apply_filters(load_df(), gov_levels, fiscal_years, sectors, q)
    df = df.dropna(subset=["amount_crore_viz"])
    g = (
        df.groupby(["sector", "gov_level"], as_index=False)["amount_crore_viz"]
        .sum()
        .sort_values("amount_crore_viz", ascending=False)
        .rename(columns={"amount_crore_viz": "amount_crore"})
    )
    return g.to_dict(orient="records")


POPULATION = {
    "union": 1438000000,
    "state": 83900000,
    "corporation": 11900000,
}


def per_capita_transform(df: pd.DataFrame) -> pd.DataFrame:
    """Divide amount by population for each gov_level to get per-capita spend."""
    df = df.copy()
    df["amount_crore"] = df.apply(
        lambda r: r["amount_crore"] * 1_00_00_000 / POPULATION.get(r["gov_level"], 1),
        axis=1,
    )
    return df


@app.get("/timeseries-percapita")
def timeseries_percapita(
    gov_levels: Optional[list[str]] = Query(default=None),
    fiscal_years: Optional[list[str]] = Query(default=None),
    sectors: Optional[list[str]] = Query(default=None),
    q: str = "",
) -> list[dict]:
    df = apply_filters(load_df(), gov_levels, fiscal_years, sectors, q)
    df = df.dropna(subset=["amount_crore_viz"])
    g = aggregate_timeseries(df)
    g = per_capita_transform(g)
    return g.to_dict(orient="records")


@app.get("/sector-mix-percapita")
def sector_mix_percapita(
    topn: int = 6,
    gov_levels: Optional[list[str]] = Query(default=None),
    fiscal_years: Optional[list[str]] = Query(default=None),
    sectors: Optional[list[str]] = Query(default=None),
    q: str = "",
) -> list[dict]:
    df = apply_filters(load_df(), gov_levels, fiscal_years, sectors, q)
    df = df.dropna(subset=["amount_crore_viz"])
    g = (
        df.groupby(["sector", "gov_level"], as_index=False)["amount_crore_viz"]
        .sum()
        .sort_values("amount_crore_viz", ascending=False)
        .rename(columns={"amount_crore_viz": "amount_crore"})
    )
    g = per_capita_transform(g)
    if topn:
        g = g.head(topn)
    return g.to_dict(orient="records")


@app.get("/sector-timeseries")
def sector_timeseries(
    gov_levels: Optional[list[str]] = Query(default=None),
    fiscal_years: Optional[list[str]] = Query(default=None),
    sectors: Optional[list[str]] = Query(default=None),
    q: str = "",
) -> list[dict]:
    df = apply_filters(load_df(), gov_levels, fiscal_years, sectors, q)
    df = df.dropna(subset=["amount_crore_viz"])
    g = (
        df.groupby(["fiscal_year", "sector", "gov_level"], as_index=False)["amount_crore_viz"]
        .sum()
        .sort_values(["fiscal_year", "gov_level", "sector"])
        .rename(columns={"amount_crore_viz": "amount_crore"})
    )
    return g.to_dict(orient="records")


@app.get("/records")
def records(
    limit: int = 300,
    gov_levels: Optional[list[str]] = Query(default=None),
    fiscal_years: Optional[list[str]] = Query(default=None),
    sectors: Optional[list[str]] = Query(default=None),
    q: str = "",
) -> list[dict]:
    df = apply_filters(load_df(), gov_levels, fiscal_years, sectors, q)
    df = df.dropna(subset=["amount_crore_viz"])
    # Prefer meaningful descriptions in top records table.
    df = df[df["clean_description"] != "N/A"]
    df = df[
        ~df["clean_description"].str.contains(
            r"(?i)\b(?:total|total assets|total liabilities|total income)\b"
        )
    ]
    cols = ["gov_level", "fiscal_year", "sector", "amount_crore_viz", "display_description", "clean_description", "row_text"]
    out = (
        df[cols]
        .rename(columns={"amount_crore_viz": "amount_crore"})
        .sort_values("amount_crore", ascending=False)
        .head(limit)
    )
    return out.to_dict(orient="records")
