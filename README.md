# Chennai Government Spending Intelligence Project

End-to-end project for **data extraction, cleaning, analysis, AI-assisted enrichment, and dashboarding** of government spending relevant to Chennai across:

- **Union Budget** (Government of India)
- **Tamil Nadu State Budget**
- **Chennai Corporation Budget (GCC)**

---

## 1) Project Goals

This project delivers:

1. A cleaned and structured dataset of government spending in Chennai context.
2. Analytical outputs (trends and sector allocations).
3. An interactive web dashboard.
4. AI-driven insights integrated into outputs and UI.
5. Clear methodology and reproducible pipeline documentation.

---

## 2) Folder Structure (What Matters)

### Core project folder

- `api_main.py` -> FastAPI backend serving dashboard data
- `web_dashboard.html` -> API-driven dashboard frontend
- `build_project_outputs.py` -> consolidation + analytics output generator
- `generate_semantic_descriptions.py` -> AI semantic cleaning for noisy descriptions
- `outputs/` -> final project outputs
- `final_output_directory/` -> packaged submission view

---

## 3) Processing Pipeline (How Data Was Built)

### A) PDF Extraction (per source PDF)

Hybrid extraction strategy:

1. `camelot` table extraction (free, structured-first)
2. `pdfplumber` table fallback
3. `tesseract` OCR fallback (for scanned/image pages)

### B) Cleaning/Normalization

Standardized fields include:

- `gov_level`
- `fiscal_year`
- `sector`
- `amount_crore`
- `row_text`
- `source_file`

### C) Consolidation

`build_project_outputs.py` merges all cleaned source-level files into one master table:

- `outputs/chennai_spending_master.csv`

### D) Analytical Outputs

Generated in `outputs/`:

- `yearly_totals_by_level.csv`
- `sector_totals_by_level.csv`
- `ANALYTICAL_REPORT.md`
- `METHODOLOGY.md`

### E) AI Enrichment

1. `ai_insights.json` from aggregated trend/sector analysis.
2. `semantic_descriptions.json` from AI semantic cleaning of noisy OCR text for better dashboard readability.

---

## 4) Key Components Used

### Data/OCR/Extraction

- `camelot`
- `pdfplumber`
- `pytesseract`
- `PyMuPDF (fitz)`
- `pandas`

### AI

- OpenAI API (`gpt-4.1-mini` used for low-cost semantic enrichment)

### Dashboard Stack

- **Backend:** FastAPI (`api_main.py`)
- **Frontend:** HTML + JS + Plotly (`web_dashboard.html`)

---

## 5) How to Run (End User)

### Step 1: Start API backend

```bash
uvicorn api_main:app --host 127.0.0.1 --port 8000 --reload
```

### Step 2: Serve dashboard frontend

```bash
python3 -m http.server 5500
```

### Step 3: Open dashboard

- `http://127.0.0.1:5500/web_dashboard.html`

---

## 6) Output Files (Final Deliverables)

Inside `outputs/`:

- `chennai_spending_master.csv` -> cleaned consolidated dataset
- `yearly_totals_by_level.csv` -> year-wise totals by Union/State/Corporation
- `sector_totals_by_level.csv` -> sector allocation by level
- `ai_insights.json` -> AI-generated insight summary
- `semantic_descriptions.json` -> AI-enhanced cleaned descriptions
- `ANALYTICAL_REPORT.md` -> key trend/sector report
- `METHODOLOGY.md` -> technical methodology

---

## 7) Data Quality Notes

- Scanned PDFs can produce OCR noise (especially in headings/totals).
- Outlier control and semantic cleaning are applied in API layer for dashboard readability.
- Raw extraction artifacts are retained for auditability and traceability.

---

## 8) Recommended Next Improvements

1. Add ward/zone geospatial mapping for true map visualizations.
2. Improve deduplication logic for repeated TOTAL lines across OCR pages.
3. Train domain-specific sector classifier for better non-`other` classification.
4. Add automated validation tests for schema and value ranges.
