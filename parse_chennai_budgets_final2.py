#!/usr/bin/env python3
"""
Parse chennai_budget_all_csvs/ files and generate clean corporation budget records.

Strategy:
- 2021-22 to 2023-24: Municipal Fund Income & Expenditure abstract ONLY
- 2024-25: Budget at a Glance summary ONLY (skip detailed schedules)
- 2025-26: Budget at a Glance (Advances) + detailed Revenue Expenditure TOTAL
- 2026-27: Budget at a Glance summary ONLY (skip detailed schedules)
"""

import csv
import re
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).parent / "chennai_budget_all_csvs"
OUT = Path(__file__).parent / "chennai_corporation_clean.csv"


def rupees_to_crore(s):
    if not s or s.strip() == "":
        return None
    cleaned = s.strip().replace(",", "").replace(" ", "").replace('"', "")
    neg = cleaned.startswith("-")
    if neg:
        cleaned = cleaned[1:]
    try:
        val = float(cleaned)
        return (-val if neg else val) / 1e7
    except ValueError:
        return None


def is_municipal_fund_abstract_page(page_text):
    pt = page_text.upper()
    if "MUNICIPAL FUND" not in pt:
        return False
    if "INCOME AND EXPENDITURE" not in pt:
        return False
    if "BALANCE SHEET" in pt:
        return False
    if "CAPITAL FUND" in pt:
        return False
    if "ELEMENTARY EDUCATION" in pt:
        return False
    if "EARMARKED FUND" in pt:
        return False
    if "NOTES OF ACCOUNTS" in pt:
        return False
    if "SUB-SCHEDULE" in pt or "SUB SCHEDULE" in pt:
        return False
    if "DETAILS OF DEPARTMENT" in pt:
        return False
    if "ABSTRACT" not in pt:
        return False
    return True


def is_budget_at_a_glance_page(page_text):
    pt = page_text.upper()
    return "BUDGET AT A GLANCE" in pt or "கண்ணோட்டம்" in pt


def parse_municipal_fund_ie_abstract(text, year_key):
    records = []
    fiscal_year = year_key.replace("_", "-")
    lines = text.splitlines()
    in_expenditure = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith(("*", "-", "#", "Row", "Header", "Footer", "Task:", 
                            "Constraint", "Input:", "No markdown", "No explanations",
                            "No summaries", "No commentary", "The user", "I should",
                            "I will", "I must", "Wait,", "Self-Correction", "Double check",
                            "Check numbers", "Final Polish", "One more check", "Note:",
                            "Usually", "However", "This means", "e.g.,", "Tamil text",
                            "English text", "Text elements", "Logo at", "Year:")):
            continue
        
        if line.upper() == "EXPENDITURE":
            in_expenditure = True
            continue
        if line.upper() == "INCOME":
            in_expenditure = False
            continue
        if not in_expenditure:
            continue
        
        if " | " in line or ("|" in line and line.count("|") >= 3):
            parts = [p.strip() for p in line.split("|") if p.strip()]
        else:
            parts = [p.strip() for p in re.split(r'\s{2,}|\t', line) if p.strip()]
        
        if len(parts) < 4:
            continue
        
        code = parts[0]
        if not re.match(r'^\d{3}$|^[A-Z]$|^[A-Z]-\d+$', code):
            continue
        
        # Only keep expenditure account codes (200-299 range)
        if code.isdigit() and not (200 <= int(code) <= 299):
            continue
        
        if code in ("A", "B") or any(sk in " ".join(parts).upper() for sk in ["TOTAL", "EXPENDITURE OVER INCOME", "B-A"]):
            continue
        
        amounts = []
        desc_parts = []
        found_first_amount = False
        
        for p in parts[1:]:
            p_clean = p.replace(",", "").replace(" ", "")
            if re.match(r'^-?\d+(\.\d+)?$', p_clean):
                amt = rupees_to_crore(p)
                if amt is not None:
                    if not found_first_amount:
                        amounts.append(amt)
                        found_first_amount = True
                    else:
                        amounts.append(amt)
                    continue
            if not found_first_amount:
                desc_parts.append(p)
        
        if not amounts or not desc_parts:
            continue
        
        description = " ".join(desc_parts)
        
        records.append({
            "fiscal_year": fiscal_year,
            "account_code": code,
            "description": description,
            "amount_crore": amounts[0],
        })
    
    return records


def parse_budget_at_a_glance_with_context(text, year_key):
    """Extract ONLY summary expenditure rows from Budget at a Glance."""
    records = []
    base_year = int(year_key.split("_")[0])
    current_fy = f"{base_year}-{str(base_year+1)[2:]}"
    
    lines = text.splitlines()
    current_section = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if line.startswith(("*", "-", "#", "Row", "Account Head:", "Actuals", "BE ",
                            "Revised", "Budget Estimate", "Column", "Section",
                            "Sl.No", "Double check", "Check numbers", "No markdown",
                            "No explanations", "No summaries", "No commentary", "Drafting",
                            "Wait,", "Self-Correction", "Header", "Title:", "Input:",
                            "Task:", "Constraint", "Image content", "Text elements",
                            "Logo at", "Tamil text", "English text", "Year:", "There is no",
                            "The user", "I should", "I will", "I must", "This means",
                            "Usually", "However", "Note:", "e.g.,")):
            continue
        if len(line) > 200:
            continue
        
        line_upper = line.upper()
        if any(k in line_upper for k in ["REVENUE ACCOUNT", "வருவாய் கணக்கு"]):
            current_section = "revenue"
            continue
        if any(k in line_upper for k in ["CAPITAL ACCOUNT", "மூலதனக் கணக்கு"]):
            current_section = "capital"
            continue
        if any(k in line_upper for k in ["REVENUE ADVANCES", "வருவாய் முன்பணம்"]):
            current_section = "revenue_advances"
            continue
        if any(k in line_upper for k in ["CAPITAL ADVANCES", "மூலதன முன்பணம்"]):
            current_section = "capital_advances"
            continue
        
        m = re.match(r'^(.+?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)$', line)
        if not m:
            m = re.match(r'^(.+?)\|\s*(-?\d+(?:\.\d+)?)\s*\|\s*(-?\d+(?:\.\d+)?)\s*\|\s*(-?\d+(?:\.\d+)?)\s*\|\s*(-?\d+(?:\.\d+)?)\s*$', line)
        
        if not m:
            continue
        
        desc = m.group(1).strip().replace("|", " ").strip()
        amounts = [float(m.group(i)) for i in range(2, 6)]
        
        desc_upper = desc.upper()
        if not any(kw in desc_upper for kw in ["EXPENDITURE", "செலவுகள்", "OUT-GOINGS", "OUTGOINGS", "செலவினங்கள்"]):
            continue
        
        if "TOTAL" in desc_upper or "மொத்தம்" in desc:
            continue
        
        if current_section == "revenue":
            label = "Revenue Expenditure"
        elif current_section == "capital":
            label = "Capital Expenditure"
        elif current_section == "revenue_advances":
            label = "Revenue Advances Out-Goings"
        elif current_section == "capital_advances":
            label = "Capital Advances Out-Goings"
        else:
            continue
        
        records.append({
            "fiscal_year": current_fy,
            "description": label,
            "amount_crore": amounts[3],  # Last column = BE current year
        })
    
    return records


def parse_revenue_expenditure_total(text, year_key):
    """Parse detailed Revenue Expenditure page and extract ONLY the TOTAL row."""
    records = []
    base_year = int(year_key.split("_")[0])
    current_fy = f"{base_year}-{str(base_year+1)[2:]}"
    
    lines = text.splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith(("*", "-", "#", "Row", "Task:", "Constraint", "Input:",
                            "No markdown", "No explanations", "No summaries", "No commentary",
                            "The user", "I should", "I will", "Header", "Title:")):
            continue
        if len(line) > 200:
            continue
        
        # Look for TOTAL row with 4 numbers
        # e.g., "மொத்தம் TOTAL    4342.40    4727.12    5439.10    5214.09"
        if "TOTAL" not in line.upper() and "மொத்தம்" not in line:
            continue
        
        m = re.match(r'^.+?TOTAL\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)$', line, re.IGNORECASE)
        if not m:
            m = re.match(r'^.+?TOTAL\|\s*(-?\d+(?:\.\d+)?)\s*\|\s*(-?\d+(?:\.\d+)?)\s*\|\s*(-?\d+(?:\.\d+)?)\s*\|\s*(-?\d+(?:\.\d+)?)\s*$', line, re.IGNORECASE)
        
        if m:
            amounts = [float(m.group(i)) for i in range(1, 5)]
            records.append({
                "fiscal_year": current_fy,
                "description": "Revenue Expenditure",
                "amount_crore": amounts[3],  # Last column = BE current year
            })
            break  # Only take first TOTAL row
    
    return records


def is_revenue_expenditure_total_page(page_text):
    """Check if page is a detailed Revenue Expenditure schedule with TOTAL."""
    pt = page_text.upper()
    return ("REVENUE" in pt and "EXPENDITURE" in pt and 
            "ESTABLISHMENT" in pt and "TOTAL" in pt and "ABSTRACT" not in pt)


def sector_from_description(desc):
    desc_upper = desc.upper()
    
    if desc in ["Revenue Expenditure", "Revenue Advances Out-Goings"]:
        return "other"
    if desc == "Capital Expenditure":
        return "infrastructure"
    if desc == "Capital Advances Out-Goings":
        return "infrastructure"
    
    if any(k in desc_upper for k in ["OPERATION AND MAINTENANCE", "O&M", "WATER SUPPLY",
                                       "SEWERAGE", "DRAINAGE", "ROADS", "STREET LIGHT",
                                       "SOLID WASTE", "PUBLIC HEALTH", "STORM WATER"]):
        return "infrastructure"
    
    if any(k in desc_upper for k in ["EDUCATION", "SCHOOL", "ELEMENTARY EDUCATION"]):
        return "education"
    
    if any(k in desc_upper for k in ["HEALTH", "MEDICAL", "WELFARE", "SOCIAL", 
                                       "POVERTY", "WOMEN", "CHILD", "DISABILITY"]):
        return "social_welfare"
    
    if any(k in desc_upper for k in ["CAPITAL", "MULADANAM", "DEVELOPMENT",
                                       "CONSTRUCTION", "BUILDING", "WORKS", "PROJECT"]):
        return "infrastructure"
    
    return "other"


def main():
    all_records = []
    seen = set()
    
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
        
        file_records = []
        is_2025_26_bag = "2025_26" in year_key and "budget_at_a_glance" in doc_slug
        
        for page in pages:
            page_text = page.get("cleaned_text", "")
            
            if "budget_at_a_glance" in doc_slug:
                if is_budget_at_a_glance_page(page_text):
                    page_records = parse_budget_at_a_glance_with_context(page_text, year_key)
                    file_records.extend(page_records)
                elif is_2025_26_bag and is_revenue_expenditure_total_page(page_text):
                    # For 2025-26, also extract Revenue Expenditure TOTAL from detailed page
                    page_records = parse_revenue_expenditure_total(page_text, year_key)
                    file_records.extend(page_records)
            else:
                if is_municipal_fund_abstract_page(page_text):
                    page_records = parse_municipal_fund_ie_abstract(page_text, year_key)
                    file_records.extend(page_records)
        
        unique_records = []
        for r in file_records:
            key = (r["fiscal_year"], r.get("description", "").strip(), round(r["amount_crore"], 4))
            if key not in seen:
                seen.add(key)
                unique_records.append(r)
        
        print(f"  -> {len(file_records)} raw, {len(unique_records)} unique records")
        all_records.extend(unique_records)
    
    # Add Capital Expenditure for 2025-26 from 2026-27 budget_at_a_glance
    csv_file_2026 = BASE / "chennai_budget_2026_27_budget_at_a_glance.csv"
    if csv_file_2026.exists():
        print(f"Processing {csv_file_2026.name} for 2025-26 Capital Expenditure ...")
        with open(csv_file_2026, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            pages = list(reader)
        
        for page in pages:
            page_text = page.get("cleaned_text", "")
            if not is_budget_at_a_glance_page(page_text):
                continue
            
            lines = page_text.splitlines()
            current_section = None
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if line.startswith(("*", "-", "#", "Row", "Account Head:", "Actuals", "BE ",
                                    "Revised", "Budget Estimate", "Column", "Section",
                                    "Sl.No", "Double check", "Check numbers", "No markdown",
                                    "No explanations", "No summaries", "No commentary", "Drafting",
                                    "Wait,", "Self-Correction", "Header", "Title:", "Input:",
                                    "Task:", "Constraint", "Image content", "Text elements",
                                    "Logo at", "Tamil text", "English text", "Year:", "There is no",
                                    "The user", "I should", "I will", "I must", "This means",
                                    "Usually", "However", "Note:", "e.g.,")):
                    continue
                if len(line) > 200:
                    continue
                
                line_upper = line.upper()
                if any(k in line_upper for k in ["REVENUE ACCOUNT", "வருவாய் கணக்கு"]):
                    current_section = "revenue"
                    continue
                if any(k in line_upper for k in ["CAPITAL ACCOUNT", "மூலதனக் கணக்கு"]):
                    current_section = "capital"
                    continue
                
                m = re.match(r'^(.+?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)$', line)
                if not m:
                    m = re.match(r'^(.+?)\|\s*(-?\d+(?:\.\d+)?)\s*\|\s*(-?\d+(?:\.\d+)?)\s*\|\s*(-?\d+(?:\.\d+)?)\s*\|\s*(-?\d+(?:\.\d+)?)\s*$', line)
                
                if m:
                    desc = m.group(1).strip().replace("|", " ").strip()
                    amounts = [float(m.group(i)) for i in range(2, 6)]
                    if "EXPENDITURE" in desc.upper() or "செலவுகள்" in desc:
                        if "TOTAL" in desc.upper() or "மொத்தம்" in desc:
                            continue
                        if current_section == "capital":
                            key = ("2025-26", "Capital Expenditure", round(amounts[1], 4))
                            if key not in seen:
                                seen.add(key)
                                all_records.append({
                                    "fiscal_year": "2025-26",
                                    "description": "Capital Expenditure",
                                    "amount_crore": amounts[1],
                                })
                                print(f"  Added Capital Expenditure for 2025-26: ₹{amounts[1]:,.2f} crore")
                            break
            if any(r.get("fiscal_year") == "2025-26" and r.get("description") == "Capital Expenditure" for r in all_records):
                break
    
    # Write output CSV
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["gov_level", "fiscal_year", "sector", "amount_crore", "row_text", "source_file", "description"])
        
        for r in all_records:
            writer.writerow([
                "corporation",
                r["fiscal_year"],
                sector_from_description(r.get("description", "")),
                round(r["amount_crore"], 4),
                r.get("description", ""),
                f"chennai_budget_all_csvs/{csv_file.name if 'csv_file' in dir() else 'various'}",
                r.get("description", ""),
            ])
    
    print(f"\nWrote {len(all_records)} clean corporation records to {OUT}")
    
    year_totals = defaultdict(float)
    for r in all_records:
        year_totals[r["fiscal_year"]] += r["amount_crore"]
    
    print("\nYearly totals (corporation expenditure, crore):")
    for fy in sorted(year_totals.keys()):
        print(f"  {fy}: ₹{year_totals[fy]:,.2f} crore")


if __name__ == "__main__":
    main()
