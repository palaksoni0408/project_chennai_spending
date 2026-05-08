#!/usr/bin/env python3
"""
Parse chennai_budget_all_csvs/ files and generate clean corporation budget records
for integration into chennai_spending_master.csv.

Data sources:
- 2020-21_balance_sheet: Balance sheet (Amount in Rupees) - skip, not expenditure
- 2021_22.csv: Income & Expenditure + Balance Sheets (Amount in Rupees)
- 2022_23.csv: Income & Expenditure + Balance Sheets (Amount in Rupees)
- 2023_24.csv: Income & Expenditure + Balance Sheets (Amount in Rupees)
- 2024_25_budget_at_a_glance.csv: Summary (Rs. in Crore)
- 2025_26_budget_at_a_glance.csv: Summary (Rs. in Crore)
- 2025_26_department_wise_expenditure.csv: Department-wise (Rs. in Thousand)
- 2026_27_budget_at_a_glance.csv: Summary (Rs. in Crore)
- 2026_27_department_wise_expenditure.csv: Department-wise (Rs. in Thousand)

Schema for master CSV:
    gov_level,fiscal_year,sector,amount_crore,row_text,source_file,description
"""

import csv
import re
import os
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).parent / "chennai_budget_all_csvs"
OUT = Path(__file__).parent / "chennai_corporation_clean.csv"


def rupees_to_crore(s):
    """Convert Indian number format string like '23,11,73,71,019' to crore float."""
    if not s or s.strip() == "":
        return None
    # Remove commas, spaces, quotes
    cleaned = s.strip().replace(",", "").replace(" ", "").replace('"', "")
    # Handle negative
    neg = cleaned.startswith("-")
    if neg:
        cleaned = cleaned[1:]
    try:
        val = float(cleaned)
        val = val / 1e7  # Rupees to crore
        return -val if neg else val
    except ValueError:
        return None


def parse_income_expenditure_abstract(text, year_key):
    """
    Parse the Municipal Fund Income & Expenditure abstract from 2020-2023 files.
    Extracts line items with account codes, descriptions, and amounts in Rupees.
    Returns list of dicts: {fiscal_year, account_code, description, amount_crore, section}
    """
    records = []
    fiscal_year = year_key.replace("_", "-")
    
    # Look for the abstract table pattern
    # Format: 110    TAX REVENUE(DEMAND)    I-01    23,11,73,71,019    13,14,49,36,963
    # We want the CURRENT year amount (first amount column after schedule number)
    
    # Also handle format: 110    TAX REVENUE(DEMAND)    I-01    23,11,73,71,019    13,14,49,36,963
    # Or: 110 TAX REVENUE(DEMAND) I-01 23,11,73,71,019 13,14,49,36,963
    
    lines = text.splitlines()
    in_abstract = False
    section = ""
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Detect section headers
        if line.upper() in ("INCOME", "EXPENDITURE", "ABSTRACT"):
            section = line.upper()
            in_abstract = True
            continue
            
        if not in_abstract:
            continue
            
        # Try to parse line items
        # Pattern: code  description  schedule  amount1  amount2
        # Split by multiple spaces or tabs
        parts = [p.strip() for p in re.split(r'\s{2,}|\t', line) if p.strip()]
        
        if len(parts) >= 4:
            # Check if first part is an account code (numeric or like "110", "A", "B")
            code = parts[0]
            if re.match(r'^\d{3}$|^[A-Z]$|^[A-Z]-\d+$', code):
                # Find amounts - look for Indian number format
                amounts = []
                for p in parts[1:]:
                    if re.match(r'^-?[\d,]+(\.\d+)?$', p.replace(",", "")) or re.match(r'^-?[\d,]+$', p):
                        # This looks like a number
                        amt = rupees_to_crore(p)
                        if amt is not None and amt > 0:
                            amounts.append(amt)
                
                if amounts:
                    # Description is everything between code and first amount
                    desc_parts = []
                    for p in parts[1:]:
                        if re.match(r'^-?[\d,]+(\.\d+)?$', p.replace(",", "")) or re.match(r'^-?[\d,]+$', p):
                            break
                        desc_parts.append(p)
                    
                    description = " ".join(desc_parts)
                    # Skip totals and subtotals
                    if any(skip in description.upper() for skip in ["TOTAL", "EXPENDITURE OVER INCOME", "A-B", "B ", "A "]):
                        continue
                    if code in ("A", "B"):
                        continue
                        
                    # Take first valid amount (current year)
                    amount_crore = amounts[0]
                    
                    records.append({
                        "fiscal_year": fiscal_year,
                        "account_code": code,
                        "description": description,
                        "amount_crore": amount_crore,
                        "section": section,
                    })
    
    return records


def parse_budget_at_a_glance(text, year_key):
    """
    Parse Budget at a Glance files (2024-25 onwards).
    These have data in Rs. Crore with multiple year columns.
    
    Only extracts actual budget line items (Receipts, Expenditure, Deficit, Surplus,
    Recoveries, Out-Goings) — skips all extraction prompt / instruction text.
    
    Returns list of dicts with fiscal_year mapped correctly.
    """
    records = []
    
    # Valid budget line item keywords that must appear in the description
    VALID_KEYWORDS = [
        "Receipts", "Expenditure", "Deficit", "Surplus",
        "Recoveries", "Out-Goings", "Out Goings", "OutGoings",
        "வரவுகள்", "செலவுகள்", "பற்றாக்குறை", "மிகை",
        "பிடித்தங்கள்", "செலவினங்கள்",
    ]
    
    # Lines to skip (extraction prompt / thinking markers)
    SKIP_PREFIXES = ("*", "-", "#", "Row", "Account Head:", "Actuals", "BE ", "RE ",
                     "Budget Estimate", "Revised Estimate", "Column", "Section",
                     "Sl.No", "Double check", "Check numbers", "No markdown",
                     "No explanations", "No summaries", "No commentary", "Drafting",
                     "Wait," , "Self-Correction", "Header", "Title:", "Input:",
                     "Task:", "Constraint", "Image content", "Text elements",
                     "Logo at", "Tamil text", "English text", "Year:", "There is no",
                     "The user", "I should", "I will", "I must", "This means",
                     "Usually", "However", "Note:", "e.g.,")
    
    lines = text.splitlines()
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Skip any line that looks like extraction prompt / thinking
        if line.startswith(SKIP_PREFIXES):
            continue
        if any(line.startswith(p) for p in SKIP_PREFIXES):
            continue
        if len(line) > 200:
            continue  # Likely a long instruction sentence
        
        # Try to match: Description + 4 numbers
        m = re.match(r'^(.+?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)$', line)
        if not m:
            m = re.match(r'^(.+?)\|\s*(-?\d+(?:\.\d+)?)\s*\|\s*(-?\d+(?:\.\d+)?)\s*\|\s*(-?\d+(?:\.\d+)?)\s*\|\s*(-?\d+(?:\.\d+)?)\s*$', line)
        
        if not m:
            continue
        
        desc = m.group(1).strip()
        amounts = [float(m.group(i)) for i in range(2, 6)]
        
        # Must contain at least one valid budget keyword
        desc_upper = desc.upper()
        if not any(kw.upper() in desc_upper for kw in VALID_KEYWORDS):
            continue
        
        # Skip totals and opening balance
        if any(skip in desc_upper for skip in ["TOTAL", "OPENING BALANCE", "NET SURPLUS", "NET DEFICIT"]):
            continue
        
        # Map amounts to fiscal years based on the file's year_key
        # For 2024_25 file: cols = [Actuals 2022-23, BE 2023-24, RE 2023-24, BE 2024-25]
        # For 2025_26 file: cols = [Actuals 2023-24, BE 2024-25, RE 2024-25, BE 2025-26]
        # For 2026_27 file: cols = [Actuals 2024-25, BE 2025-26, RE 2025-26, BE 2026-27]
        
        base_year = int(year_key.split("_")[0])
        fy_mapping = [
            f"{base_year-2}-{str(base_year-1)[2:]}",  # Actuals two years back
            f"{base_year-1}-{str(base_year)[2:]}",    # BE previous year
            f"{base_year-1}-{str(base_year)[2:]}",    # RE previous year
            f"{base_year}-{str(base_year+1)[2:]}",    # BE current year
        ]
        
        for i, (fy, amt) in enumerate(zip(fy_mapping, amounts)):
            records.append({
                "fiscal_year": fy,
                "description": desc,
                "amount_crore": amt,
                "column_type": ["actuals", "be_prev", "re_prev", "be_current"][i],
            })
    
    return records


def parse_department_wise(text, year_key):
    """
    Parse department-wise expenditure files (2025-26, 2026-27).
    Amounts are in Rs. Thousand.
    
    Returns list of dicts.
    """
    records = []
    
    SKIP_PREFIXES = ("*", "-", "#", "Row", "Department Code", "Function Code",
                     "D.P. Code", "Account Head", "Reference", "Actuals", "BE ",
                     "Revised", "Budget Estimate", "Column", "Section",
                     "No markdown", "No explanations", "No summaries", "No commentary",
                     "Task:", "Input:", "Constraint", "The user", "I should", "I will")
    
    lines = text.splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith(SKIP_PREFIXES) or any(line.startswith(p) for p in SKIP_PREFIXES):
            continue
        if len(line) > 200:
            continue
        
        # Pattern: 210-ESTABLISHMENT EXPENSES BUDGET | FORM NO F2 | 173777 | 215285 | 203016 | 219716
        # Groups: 1=code, 2=desc, 3=form_ref, 4=amt1, 5=amt2, 6=amt3, 7=amt4
        m = re.match(r'^(\d{3})[-\s]+(.+?)\s*\|\s*(.+?)\s*\|\s*(-?\d+(?:\.\d+)?)\s*\|\s*(-?\d+(?:\.\d+)?)\s*\|\s*(-?\d+(?:\.\d+)?)\s*\|\s*(-?\d+(?:\.\d+)?)\s*$', line)
        
        if not m:
            # Pattern without form ref: 210-ESTABLISHMENT EXPENSES BUDGET 173777 215285 203016 219716
            m = re.match(r'^(\d{3})[-\s]+(.+?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)$', line)
        
        if m:
            code = m.group(1)
            desc = m.group(2).strip()
            
            # Determine number of amount groups
            if m.lastindex >= 7:
                # Has form reference group: amounts at groups 4-7
                amounts = [float(m.group(i)) / 1000 for i in range(4, 8)]
            else:
                # No form reference: amounts at groups 3-6
                amounts = [float(m.group(i)) / 1000 for i in range(3, 7)]
            
            if "TOTAL" in desc.upper():
                continue
            
            # Map to fiscal years
            base_year = int(year_key.split("_")[0])
            fy_mapping = [
                f"{base_year-2}-{str(base_year-1)[2:]}",
                f"{base_year-1}-{str(base_year)[2:]}",
                f"{base_year-1}-{str(base_year)[2:]}",
                f"{base_year}-{str(base_year+1)[2:]}",
            ]
            
            for i, (fy, amt) in enumerate(zip(fy_mapping, amounts)):
                records.append({
                    "fiscal_year": fy,
                    "account_code": code,
                    "description": desc,
                    "amount_crore": amt,
                    "column_type": ["actuals", "be_prev", "re_prev", "be_current"][i],
                })
    
    return records


def sector_from_description(desc, account_code=""):
    """Map budget line item to a sector category."""
    desc_upper = desc.upper()
    
    # Revenue / Income items
    if any(k in desc_upper for k in ["TAX REVENUE", "ASSIGNED REVENUE", "RENTAL INCOME", 
                                       "FEES AND USER CHARGES", "REVENUE GRANTS", "CONTRIBUTION",
                                       "SUBSIDIES", "INCOME FROM INVESTMENT", "INTEREST EARNED",
                                       "OTHER INCOME", "RECEIPTS", "வரவுகள்"]):
        return "revenue_admin"
    
    # Infrastructure / O&M
    if any(k in desc_upper for k in ["OPERATION AND MAINTENANCE", "O&M", "WATER SUPPLY",
                                       "SEWERAGE", "DRAINAGE", "ROADS", "STREET LIGHT",
                                       "SOLID WASTE", "PUBLIC HEALTH", "STORM WATER"]):
        return "infrastructure"
    
    # Education
    if any(k in desc_upper for k in ["EDUCATION", "SCHOOL", "ELEMENTARY EDUCATION"]):
        return "education"
    
    # Social welfare / health
    if any(k in desc_upper for k in ["HEALTH", "MEDICAL", "WELFARE", "SOCIAL", 
                                       "POVERTY", "WOMEN", "CHILD", "DISABILITY"]):
        return "social_welfare"
    
    # Capital / Development
    if any(k in desc_upper for k in ["CAPITAL", "MULADANAM", "மூலதன", "DEVELOPMENT",
                                       "CONSTRUCTION", "BUILDING", "WORKS", "PROJECT"]):
        return "infrastructure"
    
    # Admin / Establishment
    if any(k in desc_upper for k in ["ESTABLISHMENT", "ADMINISTRATIVE", "SALARIES", "WAGES",
                                       "PENSION", "GRATUITY", "INTEREST AND FINANCE",
                                       "DEPRECIATION", "MISCELLANEOUS", "PROGRAMME",
                                       "EXPENDITURE", "செலவுகள்"]):
        return "other"
    
    # Default
    return "other"


def main():
    all_records = []
    
    index_path = BASE / "chennai_budget_index.csv"
    with open(index_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        index_rows = list(reader)
    
    for row in index_rows:
        csv_file = BASE / row["csv_file"]
        year_key = row["year_key"]
        doc_slug = row["document_slug"]
        
        if not csv_file.exists():
            print(f"SKIP: {csv_file} not found")
            continue
        
        print(f"Processing {csv_file.name} ...")
        
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            pages = list(reader)
        
        # Combine all cleaned_text from all pages
        all_text = "\n".join(p["cleaned_text"] for p in pages)
        
        records = []
        
        if "budget_at_a_glance" in doc_slug:
            records = parse_budget_at_a_glance(all_text, year_key)
        elif "department_wise" in doc_slug:
            records = parse_department_wise(all_text, year_key)
        else:
            # 2020-2023 detailed files
            records = parse_income_expenditure_abstract(all_text, year_key)
        
        print(f"  -> Extracted {len(records)} records")
        
        for r in records:
            # Add metadata
            r["gov_level"] = "corporation"
            r["source_file"] = f"chennai_budget_all_csvs/{csv_file.name}"
            r["sector"] = sector_from_description(r.get("description", ""), r.get("account_code", ""))
            r["row_text"] = r.get("description", "")
            
            all_records.append(r)
    
    # Write output CSV matching master schema
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["gov_level", "fiscal_year", "sector", "amount_crore", "row_text", "source_file", "description"])
        
        for r in all_records:
            writer.writerow([
                r["gov_level"],
                r["fiscal_year"],
                r["sector"],
                round(r["amount_crore"], 4),
                r["row_text"],
                r["source_file"],
                r.get("description", ""),
            ])
    
    print(f"\nWrote {len(all_records)} clean corporation records to {OUT}")
    
    # Print summary by year
    year_totals = defaultdict(float)
    for r in all_records:
        year_totals[r["fiscal_year"]] += r["amount_crore"]
    
    print("\nYearly totals (corporation, crore):")
    for fy in sorted(year_totals.keys()):
        print(f"  {fy}: ₹{year_totals[fy]:,.2f} crore")


if __name__ == "__main__":
    main()
