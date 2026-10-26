# Wind Signal — UK day-ahead wind desk

A focused decision-support pilot for a UK utility trading desk. It shows the latest Elexon national wind forecast available before a configurable day-ahead cutoff, the eventual half-hourly wind outturn, and a quantified forecast error review for January 2026.

## Product scope

- Select any January 2026 delivery day and a previous-day decision cutoff (default 10:00 UK time).
- See the forecast vintage that would have been available at that cutoff, paired with national wind actuals from Elexon.
- Review MAE, RMSE, signed bias, MAPE, forecast coverage, and matched settlement periods.
- Export all 48 half-hour settlement periods to CSV.
- Synthetic data is only used as a clearly labelled preview when live Elexon data is unreachable or returns no forecast coverage.

This pilot isolates wind. It does not include demand, thermal availability, prices, risk limits, reserve, imbalance, or an executable purchase recommendation. Positive error means forecast > actual and creates more risk of buying too little elsewhere; negative error means forecast < actual and creates more risk of buying too much elsewhere.

## Project structure

```text
wind-signal/
├── backend/
│   ├── app/
│   │   ├── api/routes.py           # Health and day-ahead dashboard endpoints
│   │   ├── main.py                 # FastAPI app and CORS
│   │   └── services/
│   │       ├── elexon.py           # Async Elexon API client
│   │       ├── analysis.py         # Vintage selection, matching, error metrics
│   │       └── preview.py          # Explicitly synthetic outage/demo fallback
│   └── Dockerfile
├── frontend/
│   ├── src/                        # Dashboard, chart, filters, CSV export and styles
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.ts              # Local API proxy
│   └── vercel.json                 # Hosted frontend API rewrite placeholder
├── docker-compose.yml              # Local React and FastAPI services
├── Procfile                        # Heroku Python process entrypoint
├── requirements.txt
├── docs/
│   ├── VIDEO_RUN_OF_SHOW.md         # Pitch and technical-review recording guide
│   └── TECH_REVIEW.md               # Architecture and methodology notes
├── .gitignore
├── .dockerignore
└── README.md
```

## Run with Docker

From this directory:

```sh
docker compose up --build
```

Open <http://localhost:5173>. API docs are at <http://localhost:8000/docs>; health is at <http://localhost:8000/api/health>. Stop with `Ctrl+C`; `docker compose down` removes the containers.

## Run without Docker

Backend, from `wind-signal/`:

```sh
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --app-dir backend
```

In another terminal:

```sh
cd frontend
npm install
npm run dev
```

The app is at <http://localhost:5173>.

## Data and calculation

The backend calls Elexon's public BMRS Insights API, which does not require an API key:

- [FUELHH stream](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream) — filter `fuelType = WIND`, use `startTime` and `generation` as actual national wind output.
- [WINDFOR stream](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream) — use `startTime`, `publishTime`, and `generation` for the forecast issue history.

For a selected delivery date, the default cutoff is 10:00 Europe/London on the previous day. Per half-hour, the backend chooses the record with the greatest `publishTime` no later than that cutoff, then joins the wind actual by `startTime`. The cutoff hour is adjustable in the UI. The current initial deployment may show the labelled synthetic preview if provider access is unavailable; a live-mode badge and source label distinguish provider records.

Error is defined as `forecast − actual` in MW. MAE is the average absolute error; RMSE is the square root of the mean squared error; bias is the signed mean error (positive means over-forecast); MAPE is mean absolute percentage error and omits actual values below 100 MW to avoid unstable percentages near zero. Scores use only matched half-hours. Forecast coverage is forecast periods divided by 48.

## Deploy

The repository is prepared for a Vercel React frontend and a Heroku Python API. Create a Heroku app from the repository root with the Python buildpack (root `requirements.txt` and `Procfile` run FastAPI from `backend/`). Create a Vercel project from the `frontend/` root and replace `YOUR-HEROKU-APP` in `frontend/vercel.json` with the API hostname. Alternatively, deploy both Docker services to a Docker host that supports Compose.

**Public repository:** [github.com/Megharajgit/abcdefg](https://github.com/Megharajgit/abcdefg). **Hosted app:** pending deployment.

## Assessment notes

- [Two-part video run-of-show](docs/VIDEO_RUN_OF_SHOW.md) is designed to fit within the requested 10-minute limit.
- [Technical review notes](docs/TECH_REVIEW.md) cover architecture, methods, and limitations.
- AI assistance was used to draft and implement the application code and documentation. Data assumptions and analysis design are described above.

## Known limitations

- The cutoff is an explicit pilot assumption, not an exchange gate-closure guarantee; the trading desk should confirm the operational decision time.
- Historical API query behaviour should be checked against a known settlement day during deployment. In particular, confirm the provider's `from`/`to` filtering semantics and payload fields before relying on live scores.
- The dashboard studies forecast quality only. It does not determine the utility's net load or calculate a procurement volume without demand and other generation inputs.
- Elexon publishes source records subject to its data licence and API terms.
