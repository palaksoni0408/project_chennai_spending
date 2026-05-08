#!/usr/bin/env python3
"""Rebuild chennai_spending_master.csv by replacing corrupted corporation data with clean records."""

import csv
from pathlib import Path

MASTER = Path(__file__).parent / "chennai_spending_master.csv"
CLEAN = Path(__file__).parent / "chennai_corporation_clean.csv"
BACKUP = Path(__file__).parent / "chennai_spending_master_backup.csv"

# Create backup
if MASTER.exists():
    BACKUP.write_text(MASTER.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Created backup: {BACKUP}")

# Read clean corporation records
with open(CLEAN, "r", encoding="utf-8") as f:
    clean_rows = list(csv.DictReader(f))

# Read existing master, filter out corporation rows, keep union and state
with open(MASTER, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    kept_rows = [r for r in reader if r.get("gov_level", "").strip().lower() != "corporation"]

print(f"Kept {len(kept_rows)} non-corporation rows")
print(f"Adding {len(clean_rows)} clean corporation rows")

# Write new master
with open(MASTER, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(kept_rows)
    writer.writerows(clean_rows)

print(f"\nRebuilt {MASTER}")
print(f"  Total rows: {len(kept_rows) + len(clean_rows)}")

# Quick summary
from collections import defaultdict
year_totals = defaultdict(float)
with open(MASTER, "r", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r.get("gov_level") == "corporation":
            year_totals[r.get("fiscal_year", "")] += float(r.get("amount_crore", 0) or 0)

print("\nCorporation yearly totals in master CSV:")
for fy in sorted(year_totals.keys()):
    print(f"  {fy}: ₹{year_totals[fy]:,.2f} crore")
