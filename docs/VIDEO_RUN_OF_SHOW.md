# Video run-of-show (maximum 10 minutes)

Record one unlisted video with two clear chapters. Keep each overview under five minutes. Use the app in January 2026, select a date, show the selected forecast vintage, then use the period table and CSV export.

## Part 1 — Client pilot pitch (about 4 minutes)

**0:00–0:30 — The decision**  
“Before tomorrow’s delivery, the trading desk needs a defensible view of wind output and the forecast vintage available when the day-ahead decision was made. Wind Signal makes that view explicit.”

**0:30–1:15 — The desk view**  
Show the national control room, January delivery date selector, and previous-day cutoff. Explain that cutoff is adjustable and displayed in UK local time.

**1:15–2:15 — Forecast and outcome**  
Show both curves. Explain that the green curve is the latest forecast published by the cutoff for each half-hour and the blue curve is later actual output. Change the date to show the daily shape changes.

**2:15–3:15 — Quantified error**  
Explain MAE as typical absolute miss, bias as whether the forecast tends high or low, and matched periods/coverage as a completeness check. Call out positive versus negative error in procurement context without claiming that wind alone sets the purchase quantity.

**3:15–4:00 — Operational handoff**  
Show the settlement table and CSV export. Close: “This pilot gives the team forecast visibility and a transparent accuracy baseline. Next, validate the operational cutoff and connect demand and portfolio position before treating it as a procurement aid.”

## Part 2 — Internal technical review (about 4.5 minutes)

**0:00–0:40 — Architecture**  
Show the folder tree. React/Vite calls FastAPI; FastAPI fetches Elexon and normalizes the response. Docker Compose runs web and API services.

**0:40–1:40 — Data lineage**  
Open `backend/app/services/elexon.py` and explain the two stream pulls. Open `analysis.py`: filter WIND actuals; retain forecast rows published by the selected cutoff; select latest per start time; join by settlement start.

**1:40–2:40 — Metrics and controls**  
Explain formulas, coverage and matched sample. Discuss timezone-aware Europe/London cutoff and half-hour settlement periods. Point out the fallback mode is clearly marked as synthetic.

**2:40–3:40 — Frontend and API**  
Show `backend/app/api/routes.py`, `/api/dashboard`, date scope, cutoff-hour parameter, and API docs. Show `frontend/src/App.tsx` chart, filtering, and CSV export.

**3:40–4:30 — Run and limits**  
Show `docker compose up --build` and the README. State assumptions and limitations: verify upstream filter semantics and the team's cutoff; the pilot does not contain demand or other portfolio inputs, so it does not recommend a buy quantity.

Leave a few seconds for transition between chapters. Keep the total recording under 10 minutes.
