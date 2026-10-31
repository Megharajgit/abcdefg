# Technical review - Wind Signal

## Purpose and scope

Wind Signal reconstructs the national wind-generation forecast available to a utility trading team at a selected previous-day decision cutoff, then compares it with eventual Elexon FUELHH WIND generation. It is a forecast-accuracy and decision-support pilot, not a procurement optimizer: demand, prices, thermal availability and portfolio position are not inputs.

## System architecture

```text
Browser: React 19 + TypeScript + Vite
   | GET /api/dashboard?date=YYYY-MM-DD&cutoff_hour=10
   | localhost Vite proxy or same-origin Vercel service rewrite
FastAPI router
   |-- Elexon FUELHH dataset: settlementDateFrom/settlementDateTo
   `-- Elexon WINDFOR stream: publishDateTimeFrom/publishDateTimeTo
Pure analysis module: UTC-normalized timestamps -> expected half-hours -> metrics
```

`backend/app/services/elexon.py` owns upstream HTTP behavior and response-shape validation. `analysis.py` is a deterministic transformation of raw rows and has no network dependency. The route handles scope validation, explicit live-data notices and the preview fallback. The frontend controls the January 2026 date and cutoff, renders chart, coverage, accuracy metrics and settlement detail, and exports all periods as CSV.

## Source retrieval decisions

### FUELHH actuals

Do not use a publication-time window as a substitute for a delivery-time filter. The actuals request uses the FUELHH dataset endpoint with `settlementDateFrom` and `settlementDateTo` set to the requested day. The response's `startTime` is normalized and filtered against the selected local delivery day, then the `fuelType == WIND` observation is retained. For 15 January 2026, a read-only Elexon API request returned 960 fuel rows and 48 distinct WIND timestamps, from period 1 at 00:00 through period 48 at 23:30. This validates the retrieval filter and source shape only; it does not imply all forecasts matched.

### WINDFOR forecast vintages

The stream endpoint is queried by the documented publication-time parameters, from two days before the cutoff through the cutoff. This fetch window is intentionally broader than the target delivery periods because individual forecast publications contain projections across multiple start times. The analysis filters records by target `startTime` and `publishTime <= cutoff`, then chooses the latest eligible `publishTime` per source start. Equality at cutoff is allowed.

### Why 24 hourly forecasts can cover 48 half-hours

The audit's read-only WINDFOR extract for 15 January 2026 showed 24 distinct forecast start times across the target day, on the hour. This is source resolution, not missing half-hour data: Elexon describes WINDFOR as an hourly forecast and its wind forecast methodology says the hourly value is used for both settlement periods within the hour. The analysis therefore maps a selected `HH:00` source forecast to settlement starts `HH:00` and `HH:30`. A source record already at `HH:30`, if present, is matched to that exact start and wins a tie against the inherited hourly value. Forecast source hours and covered half-hour forecast periods are counted separately. This mapping is explicitly documented in the UI and is not zero-filling or interpolation.

After temporal alignment, forecast-to-actual matching is by normalized UTC half-hour `startTime`.

Elexon's developer portal describes dataset endpoints as publication-time queryable (for retrieving superseded records) and says stream endpoints return JSON without data-return restrictions. The client accepts bare arrays and metadata envelopes with `data` or `results`. There is no manual pagination for these Elexon stream requests because the provider's stream contract describes unrestricted stream responses. HTTP 429 and selected transient 5xx responses get at most two retries, respecting `Retry-After` when supplied and capping the wait at five seconds. Request timeouts are finite. Failures log endpoint, status, URL and a truncated response body.

## Time and settlement-period rules

Source timestamps with explicit offsets are normalized to UTC. Naive source timestamps are treated as UTC because the source timestamps are UTC-oriented. Decision cutoff is constructed in `Europe/London` on the previous local calendar day, then normalized to UTC for comparisons. The UI formats all timestamps explicitly in `Europe/London`, including chart axis labels.

The challenge is scoped to January 2026, when local days contain 48 half-hour periods. Expected slots are constructed as 00:00 through 23:30, advancing in UTC 30-minute increments and then displayed in UK time. Missing actuals and forecasts remain null. Zero is a valid reported generation value and is preserved. Counts are returned separately: expectedPeriods, forecastSourceHours, forecastPeriods (half-hour slots with a mapped eligible value), actualPeriods and matchedPeriods. Coverage percentages all use expected periods as denominator.

## Accuracy calculations

For each matched period, `error = forecast - actual` in MW. MAE is mean absolute error, RMSE is the square root of mean squared error, and bias is mean signed error. Those metrics use the same matched pair set. MAPE is mean absolute percentage error times 100, excluding matched actuals below 100 MW; the threshold is an exposed constant and API field so the pilot assumption is visible. Metrics and period values are not rounded in Python; display formatting is client-side. Unit tests include the specified [100, 200, 300] forecast and [90, 220, 290] actual values.

## Live and preview behavior

Network, HTTP and malformed-source failures return synthetic preview data only with `mode: preview`, a synthetic source label and an explanatory notice. A successful live response with no eligible forecast or actuals remains `mode: live`; absent values remain null, and a notice explains the missing source records. Unexpected application processing errors return HTTP 502 with server-side exception logs rather than being disguised as preview observations. Frontend has separate loading, request-error, no-match and synthetic-preview states.

## Deployment and local operation

Docker Compose runs FastAPI on 8000 and Vite on 5173; the web container proxies `/api` to the `api` service. Vercel is configured as two Services from the repository root: Vite under `frontend/`, FastAPI under `backend/`; root routing sends `/api/*` to backend and remaining paths to frontend. Browser requests use relative `/api` paths; the hard-coded localhost target exists only as Vite's local-development proxy default.

## Test strategy

`backend/tests` contains pure analysis unit tests, route tests with network dependencies monkeypatched, and upstream-client tests using `httpx.MockTransport`. It verifies cutoff boundary and look-ahead prevention, actual fuel filtering and duplicate resolution, January slot generation, partial/missing coverage, metric calculations, API scope/validation, preview labeling, query parameter choice and retry behavior. `npm run build` is the frontend TypeScript and Vite production compile. Docker Compose validation and startup are separate environment-dependent checks and must be reported only when run successfully.

## Risks and follow-up

1. Confirm the assumed 10:00 previous-day decision cutoff with the trading desk.
2. Confirm a 100 MW MAPE exclusion threshold and interpretation of the FUELHH and WINDFOR national aggregates.
3. Verify forecast coverage over all January dates and cutoffs against a second source extract before operational use.
4. Check actual Vercel deployment logs and health/dashboard endpoints after the code is pushed; configuration alone does not establish deployment success.
5. Demand, prices, portfolio position, forecast uncertainty and asset constraints are required before this tool can suggest a buy quantity.

## Historical source verification

A live read-only check for 15 January 2026 verified 960 FUELHH fuel rows including 48 distinct WIND starts; the WINDFOR selected source had 24 hourly start times. Running those actual Elexon responses through the corrected backend produced 48 expected slots, 24 forecast source hours, 48 forecast-covered half-hours, 48 actual observations and 48 matched periods. This is a coverage verification only; it does not report or assert a forecast accuracy score.
