#!/usr/bin/env python3
"""Build consolidated outputs for Chennai government spending project."""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(".")
OUT = ROOT / "chennai_spending_project" / "outputs"


def infer_year_from_path(path: Path) -> str:
    m = re.search(r"(20\d{2}[-_]\d{2})", str(path))
    if not m:
        return "unknown"
    return m.group(1).replace("_", "-")


def load_union() -> pd.DataFrame:
    p = ROOT / "union_budget" / "master_union_budget.csv"
    df = pd.read_csv(p, low_memory=False)
    df["amount_crore"] = pd.to_numeric(df["amount_crore"], errors="coerce")
    df = df.dropna(subset=["amount_crore"]).copy()
    df["gov_level"] = "union"
    df["source_file"] = str(p)
    df["row_text"] = df["description"].fillna("")
    keep = ["gov_level", "fiscal_year", "sector", "amount_crore", "row_text", "source_file"]
    return df[keep]


def load_hybrid_csvs(pattern: str, gov_level: str) -> pd.DataFrame:
    frames = []
    for p in sorted((ROOT / "budget_extraction_outputs").glob(pattern)):
        df = pd.read_csv(p, low_memory=False)
        if df.empty:
            continue
        year = infer_year_from_path(p)
        df["amount_crore"] = pd.to_numeric(df.get("amount_1"), errors="coerce")
        df["fiscal_year"] = year
        df["gov_level"] = gov_level
        df["source_file"] = str(p)
        df["row_text"] = df.get("row_text", "").astype(str)
        df["sector"] = df.get("sector", "other").fillna("other")
        frames.append(df[["gov_level", "fiscal_year", "sector", "amount_crore", "row_text", "source_file"]])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["gov_level", "fiscal_year", "sector", "amount_crore", "row_text", "source_file"]
    )


def build_master() -> pd.DataFrame:
    union_df = load_union()
    chennai_df = load_hybrid_csvs("chennai_*_hybrid/final_cleaned.csv", "corporation")
    tn_df = load_hybrid_csvs("tamilnadu_*/final_cleaned.csv", "state")
    master = pd.concat([union_df, tn_df, chennai_df], ignore_index=True)
    master["amount_crore"] = pd.to_numeric(master["amount_crore"], errors="coerce")
    master = master.dropna(subset=["amount_crore"]).copy()
    master["sector"] = master["sector"].fillna("other")
    return master


def build_insights(master: pd.DataFrame) -> dict:
    yearly = (
        master.groupby(["gov_level", "fiscal_year"], as_index=False)["amount_crore"]
        .sum()
        .sort_values(["gov_level", "fiscal_year"])
    )
    sector_latest = []
    for level in sorted(master["gov_level"].unique()):
        d = master[master["gov_level"] == level]
        latest = sorted(d["fiscal_year"].dropna().unique())[-1]
        s = (
            d[d["fiscal_year"] == latest]
            .groupby("sector", as_index=False)["amount_crore"]
            .sum()
            .sort_values("amount_crore", ascending=False)
        )
        sector_latest.append(
            {
                "gov_level": level,
                "latest_year": latest,
                "top_sectors": s.head(5).to_dict(orient="records"),
            }
        )

    sy = master.groupby(["gov_level", "sector", "fiscal_year"], as_index=False)["amount_crore"].sum()
    sy["zscore"] = sy.groupby(["gov_level", "sector"])["amount_crore"].transform(
        lambda s: (s - s.mean()) / (s.std(ddof=0) if s.std(ddof=0) else np.nan)
    )
    anomalies = sy[sy["zscore"].abs() >= 1.8].sort_values("zscore", ascending=False)

    return {
        "rows": int(len(master)),
        "gov_levels": sorted(master["gov_level"].unique().tolist()),
        "yearly_totals_sample": yearly.head(20).to_dict(orient="records"),
        "sector_latest": sector_latest,
        "anomaly_count": int(len(anomalies)),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    master = build_master()
    master.to_csv(OUT / "chennai_spending_master.csv", index=False)

    # deliverable-friendly exports
    yearly = master.groupby(["gov_level", "fiscal_year"], as_index=False)["amount_crore"].sum()
    yearly.to_csv(OUT / "yearly_totals_by_level.csv", index=False)

    sector = master.groupby(["gov_level", "sector"], as_index=False)["amount_crore"].sum()
    sector.to_csv(OUT / "sector_totals_by_level.csv", index=False)

    insights = build_insights(master)
    (OUT / "ai_insights.json").write_text(json.dumps(insights, indent=2))

    report = f"""# Chennai Government Spending - Analytical Report

## Scope
Union + Tamil Nadu State + Chennai Corporation cleaned outputs combined.

## Dataset summary
- Total rows: {len(master)}
- Government levels: {", ".join(sorted(master['gov_level'].unique()))}
- Fiscal years: {", ".join(sorted(master['fiscal_year'].dropna().unique())[:12])}

## Key files
- `chennai_spending_master.csv`
- `yearly_totals_by_level.csv`
- `sector_totals_by_level.csv`
- `ai_insights.json`
"""
    (OUT / "ANALYTICAL_REPORT.md").write_text(report)

    methodology = """# Methodology

## Data sources
- Union: `union_budget/master_union_budget.csv`
- State: `budget_extraction_outputs/tamilnadu_*/final_cleaned.csv`
- Corporation: `budget_extraction_outputs/chennai_*_hybrid/final_cleaned.csv`

## Pipeline
1. Ingest cleaned outputs from all levels.
2. Standardize to: gov_level, fiscal_year, sector, amount_crore, row_text, source_file.
3. Generate combined master and aggregate views.
4. Build lightweight anomaly signals via z-score.

## Notes
- OCR-origin rows may contain minor text noise.
- Amounts use the first detected numeric (`amount_1`) for state/corporation cleaned extracts.
"""
    (OUT / "METHODOLOGY.md").write_text(methodology)

    print(f"Saved project outputs in: {OUT}")
    print(f"Master rows: {len(master)}")


if __name__ == "__main__":
    main()
