# Run Professional Dashboard (Non-Streamlit)

This stack uses:
- **FastAPI** backend (`api_main.py`)
- **HTML + Plotly.js** frontend (`web_dashboard.html`)

## 1) Start API

```bash
cd "./chennai_spending_project"
uvicorn api_main:app --host 127.0.0.1 --port 8000 --reload
```

## 2) Open Frontend

Open this file in browser:

`./chennai_spending_project/web_dashboard.html`

If browser blocks local file CORS, run:

```bash
cd "./chennai_spending_project"
python3 -m http.server 5500
```

Then visit:
- `http://127.0.0.1:5500/web_dashboard.html`
