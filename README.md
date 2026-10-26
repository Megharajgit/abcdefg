# Wind Signal  UK day-ahead wind desk

A decision-support pilot for a UK utility trading desk. It displays Elexon national wind forecasts available before a configurable day-ahead cutoff, eventual half-hourly actuals, and forecast accuracy metrics for January 2026.

## Features

- Select a January 2026 delivery date and previous-day decision cutoff (default 10:00 Europe/London).
- Compare the latest forecast published by the cutoff with actual national wind generation.
- Review MAE, RMSE, signed bias, MAPE, forecast coverage, and matched settlement periods.
- Export all 48 half-hour periods to CSV.
- Clearly labelled synthetic preview values appear only when the live Elexon request fails or produces no matching forecasts.

This pilot isolates wind generation. It does not include demand, thermal availability, prices, or portfolio position and does not issue a purchase-volume recommendation.

## Run locally with Docker

From the project root:

```powershell
docker compose up --build
```

Open http://localhost:5173. API docs are at http://localhost:8000/docs. Stop the stack with Ctrl+C.

## Run locally without Docker

Backend, from the project root:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --app-dir backend
```

Open a second PowerShell window:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

## Deploy both services to Vercel

The root `vercel.json` deploys the Vite frontend and FastAPI backend as two services in one Vercel project. Keep the Vercel project root set to `./` (the repository root); do not set it to `frontend/`.

### Dashboard flow

1. Push the project to the GitHub repository.
2. In Vercel, choose **Add New!’ Project** and import `Megharajgit/abcdefg`.
3. Keep the project root at `./`, review the build configuration, and deploy.
4. Check the deployment URL at `/`, then verify `/api/health` and `/api/dashboard?date=2026-01-15&cutoff_hour=10`.

The service rewrites send `/api/*` to FastAPI and all other paths to the frontend. Vercel's current Services configuration supports defining both service roots and routing in the repository-level `vercel.json`. See [Vercel Services routing](https://vercel.com/docs/services/routing) and [FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi).

### Deploy with the Vercel CLI

From the project root:

```powershell
npm install --global vercel
vercel login
vercel link
vercel deploy --prod
```

Choose the correct personal account/team when prompted. The resulting production URL is the hosted app URL to put in the submission README and form.

**Repository:** https://github.com/Megharajgit/abcdefg  
**Hosted app:** pending Vercel deployment.

## Data source and calculations

The backend uses Elexon's public BMRS Insights API (no API key required):

- [FUELHH stream](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream): national wind actuals where `fuelType = WIND`.
- [WINDFOR stream](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream): forecast `generation`, `startTime`, and `publishTime`.

The backend requests source publication windows, selects the most recent forecast published at or before the cutoff for each half-hour, then joins actuals by `startTime`. Error is `forecast" actual` in MW. MAE is average absolute error; RMSE is square-root mean squared error; bias is signed mean error; MAPE excludes actuals below 100 MW. Scores use matched half-hours.

## Assessment notes

- `docs/VIDEO_RUN_OF_SHOW.md` contains the two-part recording outline, within the requested ten-minute total.
- `docs/TECH_REVIEW.md` explains architecture, methods, and limitations.
- AI tools were used to draft and implement the application code and documentation.

## Limitations

- The default 10:00 UK cutoff is a pilot assumption for the trading desk to confirm.
- The dashboard measures wind forecast accuracy only; without load and portfolio data it cannot determine procurement volume.
- Elexon records remain subject to Elexon's data licence and API terms.
