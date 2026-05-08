# Methodology

## Data sources
- Union: `union_budget/master_union_budget.csv`
- State: `budget_extraction_outputs/tamilnadu_*/final_cleaned.csv`
- Corporation: `budget_extraction_outputs/chennai_*_hybrid/final_cleaned.csv`

## Tools used

c

### Data processing and analysis
- `pandas` - cleaning, transformations, aggregation, CSV outputs
- `numpy` - numerical calculations and anomaly scoring support
- Python standard library (`re`, `json`, `pathlib`) - text cleanup, metadata, file orchestration

### AI-assisted enrichment
- OpenAI API (`gpt-4.1-mini`) - semantic cleanup of noisy OCR text and short description enrichment
- AI insight generation - anomaly and trend summary outputs in `ai_insights.json`

### Dashboard and serving stack
- `FastAPI` - backend API endpoints (`/kpis`, `/timeseries`, `/sector-mix`, `/records`)
- `Plotly.js` - interactive visualizations in browser
- HTML/CSS/JavaScript - frontend dashboard UI
- `uvicorn` - API application server
- `python -m http.server` - static frontend serving in local mode

### Deployment
- Render (web deployment target) for hosted dashboard/API runtime

## Pipeline
1. Ingest cleaned outputs from all levels.
2. Standardize to: gov_level, fiscal_year, sector, amount_crore, row_text, source_file.
3. Generate combined master and aggregate views.
4. Build lightweight anomaly signals via z-score.

## Notes
- OCR-origin rows may contain minor text noise.
- Amounts use the first detected numeric (`amount_1`) for state/corporation cleaned extracts.
