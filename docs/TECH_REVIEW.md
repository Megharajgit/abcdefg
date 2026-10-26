# Technical review notes

## Architecture

```text
React + TypeScript (Vite)
          │ /api proxy
          ▼
FastAPI ──┬── FUELHH stream (WIND actuals)
          └── WINDFOR stream (forecast publication history)
```

The frontend handles delivery date and cutoff selection, chart/table rendering, accessibility labels, and CSV download. The API owns upstream access, the time-zone cutoff, matching, and metrics. The source client and pure analysis logic are separate modules so the most consequential selection rule is easy to review.

## Forecast vintage rule

For each delivery start time, retain forecast rows whose `publishTime <= cutoff` and choose the maximum eligible `publishTime`. Match with FUELHH actuals on `startTime`, filtered to `fuelType == WIND`. All times are timezone-aware; the cutoff uses `Europe/London`, which is GMT in January 2026. The cutoff defaults to 10:00 on the previous local day and is visible/adjustable.

## Metrics

For matched periods, let `e = forecast − actual`:

- MAE = mean(|e|)
- RMSE = sqrt(mean(e²))
- Bias = mean(e)
- MAPE = mean(|e / actual|) × 100, excluding actual < 100 MW

Coverage is selected forecast rows / 48 expected periods. Error direction is useful context, not a standalone procurement signal.

## Reliability and safety of interpretation

Elexon calls fail into an explicit synthetic preview so the UI remains demonstrable. `mode`, `source`, and a visible warning prevent preview values from being confused with provider data. The route is intentionally scoped to January 2026. No user input is interpolated into URLs; dates are parsed and cutoff hours are bounded.

## Review items before operational use

1. Confirm exact query filters and schema for historic stream requests against Elexon docs and an independently checked settlement period.
2. Agree an operational decision cutoff with the trading desk.
3. Add demand and portfolio-level context before translating wind error into procurement actions.
4. Consider persistence/caching, upstream telemetry, and retries for a production service.
