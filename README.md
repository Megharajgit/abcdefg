# Wind Signal - UK Day-Ahead Wind Procurement Dashboard

Wind Signal is a pilot decision-support dashboard for a UK electricity trading team. It shows national wind forecasts that were available by an assumed day-ahead cutoff, compares them with Elexon wind generation outturn, and quantifies forecast error. It does not calculate residual demand or recommend a procurement volume because demand, prices, portfolio position and thermal availability are outside this assessment scope.

## Features

- Select any delivery date in January 2026 and a previous-day cutoff (default 10:00 Europe/London).
- Reconstruct the latest forecast vintage available at or before the cutoff for each half-hour, with no look-ahead.
- Compare forecast and actual wind generation in MW, including an interactive line chart and publication timestamps.
- Calculate MAE, RMSE, bias and MAPE; show expected, forecast, actual and matched period counts separately.
- Keep all 48 half-hours, nulls and partial coverage; export all periods to CSV.
- Distinguish live Elexon results from synthetic preview results and show a warning for either an upstream failure or missing live records.

## Architecture and data flow

```text
React + TypeScript (Vite)
  | same-origin /api/* (Vite proxy locally; Vercel service rewrite in deployment)
  v
FastAPI
  |-- FUELHH dataset: delivery date by settlementDateFrom/To; keep WIND rows
  `-- WINDFOR stream: publication window; choose latest eligible issue per startTime
  v
UTC timestamp matching -> 48 delivery slots -> statistics -> dashboard JSON
```

The backend uses Python and has no Pandas dependency because these two small, one-day series are straightforward to normalize with standard-library datetime and list operations.

## Repository structure

```text
docker-compose.yml                 Local API and web services
vercel.json                        Root Vercel Services routing
Procfile                           Platform API startup command
requirements.txt                   Root Python runtime dependencies
.dockerignore / .gitignore         Build and version-control exclusions
docs/
  TECH_REVIEW.md                   Architecture and implementation decisions
  VIDEO_RUN_OF_SHOW.md             Customer and technical demo guide
backend/
  app/api/routes.py              FastAPI health and dashboard endpoints
  app/services/elexon.py         Elexon request client, retries and response validation
  app/services/analysis.py       Timestamp normalization, matching and metrics
  app/services/preview.py        Clearly labelled synthetic preview only
  tests/                          Pytest analysis, API and upstream-client tests
  Dockerfile
  requirements.txt
  requirements-dev.txt
frontend/
  src/App.tsx                     Dashboard and accuracy review views
  src/style.css                   Wind Signal design system and responsive styling
  vite.config.ts                  Local /api proxy configuration
  Dockerfile
  package.json / package-lock.json
  index.html
```

## Data sources and retrieval

- [Elexon FUELHH dataset documentation](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH) describes half-hourly generation by fuel type. For historical actuals this app calls the FUELHH dataset endpoint with `settlementDateFrom` and `settlementDateTo` for the selected delivery date, then retains only records whose `fuelType` is `WIND`. This avoids confusing delivery-period start times with record publication times. The returned `startTime` is still checked and used for the join. See also the [FUELHH stream documentation](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream).
- [Elexon WINDFOR stream documentation](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream) describes forecast records. The app requests a publication window ending at the decision cutoff and filters each returned record by its delivery `startTime`.
- Elexon's [Insights API developer portal](https://developer.data.elexon.co.uk/) explains that dataset endpoints can retrieve records by publication times and that stream endpoints return JSON without data-return restrictions. The client accepts array and `{ "data": [...] }` JSON shapes, applies bounded retries for HTTP 429 and transient 5xx responses, and logs request failures. No API key is required.

The historical API check used during this audit confirmed that `FUELHH` settlement-date parameters returned 960 fuel rows for 15 January 2026, including 48 distinct WIND start times from 00:00 through 23:30. A read-only `WINDFOR` query returned one hourly source value per target hour for that date. This explains a raw exact-start comparison of 24 hourly forecast records against 48 half-hour periods. Elexon describes [WINDFOR as hourly](https://bmrs.elexon.co.uk/wind-generation) and its [forecast methodology](https://bscdocs.elexon.co.uk/bsc-module/category-3-documents/loss-of-load-probability-calculation-methodolgy-statement/v-2-0/id-62e1390451cbb100074edf5e) states the hourly forecast is used for both settlement periods in that hour; the analysis therefore maps each hourly value to its two half-hours. It does not create missing values or zero-fill them. Source-hour count is exposed separately from half-hour forecast coverage. The API checks validate retrieval and cadence, not a forecast-accuracy result. No synthetic values are presented as observed Elexon data.

## Forecast selection and time handling

The default pilot decision time is 10:00 Europe/London on the previous local day. The product manager must confirm this cutoff with the trading team before operational use. WINDFOR records are parsed into timezone-aware datetimes and normalized to UTC for matching. For each of the 48 delivery-period starts, records published after the cutoff are excluded and the record with the latest eligible `publishTime` is selected. A record published exactly at the cutoff is eligible. Actuals are matched on `startTime`; duplicate actuals are resolved by latest publication time and then source revision where available.

Displayed timestamps use Europe/London. January 2026 is GMT. Missing source observations remain `null`; they are never filled with zero. The dashboard distinguishes expected (48), forecast, actual and matched counts. MAPE ignores matched periods with actual generation below 100 MW; the threshold is exposed in API metrics and should be confirmed with the client.

## Accuracy metrics

For valid matched pairs, error `e = forecast - actual` in MW.

- MAE = mean(`abs(e)`) in MW.
- RMSE = `sqrt(mean(e * e))` in MW.
- Bias = mean(`e`) in MW; positive means forecast overestimated wind.
- MAPE = mean(`abs(e / actual)`) * 100, excluding actual values below 100 MW.

The other three metrics use exactly the same matched pairs. Calculations retain full source precision; presentation formatting is applied in the frontend.

## Run with Docker Compose

Prerequisite: install and start Docker Desktop. From the repository root:

```powershell
docker compose up --build
```

Open http://localhost:5173. The API health endpoint is http://localhost:8000/api/health and interactive API docs are at http://localhost:8000/docs. Stop containers with Ctrl+C, or run `docker compose down` in another terminal.

## Run locally without Docker

Backend (PowerShell, repository root):

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements-dev.txt
uvicorn app.main:app --reload --app-dir backend
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. Vite forwards `/api` to `http://localhost:8000` by default. Set `VITE_API_PROXY_TARGET` only when the local API runs at another address.

## Tests and production build

From the repository root, with the development dependencies installed:

```powershell
py -3 -m pytest backend/tests -q
cd frontend
npm ci
npm run build
```

Tests mock upstream Elexon HTTP requests; the suite does not depend on Elexon availability or fixed live records.

## Vercel deployment

The repository's root `vercel.json` configures Vercel Services for `frontend/` (Vite) and `backend/` (FastAPI), routing `/api/*` to the API service and other paths to the frontend. Import the repository with the project root set to `./` (repository root), then inspect the deployment logs and verify the three URLs below.

- Repository: https://github.com/Megharajgit/abcdefg
- Hosted application: https://abcdefg-lac.vercel.app/
- Health check: https://abcdefg-lac.vercel.app/api/health

The repository contains deployment configuration, but this README does not claim that a new deployment was verified as part of this code audit. Vercel deployment status and any configuration errors must be checked in the Vercel dashboard after pushing or importing the changes.

## Limitations and assessment boundary

- January 2026 only; the app creates 48 periods because this month is not a UK daylight-saving transition month.
- The 10:00 previous-day cutoff and MAPE 100 MW threshold are pilot assumptions for client confirmation.
- Forecast accuracy is not procurement volume. Load, contract position, market prices, asset availability and risk appetite are not included.
- If Elexon is unreachable or returns an invalid response, an explicit synthetic preview can be displayed with the reason. A valid but empty live response stays in live mode and is not converted to preview data.
- The Elexon datasets and their use are subject to the BMRS data licence and API terms.

## AI disclosure

AI tools were used to assist with code review, implementation, tests and documentation. Human review and deterministic unit tests are used to check the resulting work.

Corrected end-to-end Elexon check: for 15 January 2026 at the 10:00 previous-day cutoff, the backend generated 48 expected periods, selected 24 hourly source forecast points, mapped them to 48 half-hour forecast periods, retrieved 48 WIND actual periods, and matched all 48. These are coverage counts, not forecast-accuracy scores.
