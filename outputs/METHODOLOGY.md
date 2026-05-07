# Methodology

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
