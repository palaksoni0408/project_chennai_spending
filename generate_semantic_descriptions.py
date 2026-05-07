#!/usr/bin/env python3
"""Generate AI-enhanced semantic descriptions for noisy row_text values."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
from openai import OpenAI

BASE = Path("./chennai_spending_project/outputs")
MASTER = BASE / "chennai_spending_master.csv"
OUT = BASE / "semantic_descriptions.json"
MODEL = os.getenv("BUDGET_GPT_MODEL", "gpt-4.1-mini")
LIMIT = 300  # keep cost low


def main() -> None:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise EnvironmentError("OPENAI_API_KEY is not set.")
    client = OpenAI(api_key=key)

    df = pd.read_csv(MASTER, low_memory=False)
    df["amount_crore"] = pd.to_numeric(df["amount_crore"], errors="coerce")
    df = df.dropna(subset=["amount_crore"])
    df["row_text"] = df["row_text"].fillna("").astype(str)
    df = df[df["row_text"].str.len() > 3]

    # Prioritize high-impact/noisy rows
    top = (
        df.sort_values("amount_crore", ascending=False)["row_text"]
        .drop_duplicates()
        .head(LIMIT)
        .tolist()
    )

    mapping: dict[str, str] = {}
    batch_size = 40
    for i in range(0, len(top), batch_size):
        batch = top[i : i + batch_size]
        prompt = (
            "Rewrite each budget row into a clean, meaningful short description (max 10 words), "
            "without large numbers/codes. Keep finance meaning. "
            "Return strict JSON object mapping original text to cleaned description.\n\nRows:\n"
            + "\n".join(f"- {x}" for x in batch)
        )
        try:
            resp = client.responses.create(
                model=MODEL,
                input=prompt,
                temperature=0,
                text={"format": {"type": "json_object"}},
            )
            txt = (resp.output_text or "").strip()
            data = json.loads(txt)
            if isinstance(data, dict):
                for k, v in data.items():
                    mapping[str(k)] = str(v).strip()
            print(f"batch {i//batch_size + 1}: mapped {len(data) if isinstance(data, dict) else 0}")
        except Exception as exc:
            print(f"batch {i//batch_size + 1}: error {exc}")

    OUT.write_text(json.dumps(mapping, indent=2))
    print(f"saved {OUT} with {len(mapping)} mappings")


if __name__ == "__main__":
    main()
