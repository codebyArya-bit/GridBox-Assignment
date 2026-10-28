# GridBox — Day-Ahead Wind Intelligence

Full-stack React / TypeScript and Python FastAPI analytical pilot for UK electricity purchasing teams.

**Public app:** https://gridbox-wind-web.vercel.app
**Public backend:** https://gridbox-wind-api.vercel.app/api/health
**GitHub Actions:** [CI](https://github.com/codebyArya-bit/GridBox-Assignment/actions/workflows/ci.yml), [live Elexon](https://github.com/codebyArya-bit/GridBox-Assignment/actions/workflows/elexon-live.yml), [public deployment](https://github.com/codebyArya-bit/GridBox-Assignment/actions/workflows/deployment-smoke.yml).

## Requirements and methodology

- The assignment covers purchasing decisions made **1–31 January 2026**. The simulated purchase decisions relate to wind generation delivered the next day (2 January–1 February).
- Actuals are from the Elexon BMRS **FUELHH** national 30-minute dataset, filtered for **WIND**.
- Forecast revisions are from the Elexon BMRS **WINDFOR** historical dataset. Each half-hour interval uses the latest revision whose publishTime is at or before the assumed buying cutoff.
- Default decision cutoff **11:00 Europe/London** on the buying date is configurable. This is explicitly a **pilot assumption, not a verified market gate closure**.
- Mean absolute error (MAE), root mean squared error (RMSE), signed bias and matching coverage are calculated only for aligned pairs. Errors are in MW, signed error is forecast minus actual. Missing data stays missing.
- Demand is outside the assignment dataset scope, so the product **does not calculate total grid shortfall or net procurement amount**.
- If Elexon is unreachable, the backend reports an upstream error rather than replacing measurements with synthetic values.

## Architecture

- `frontend/`: responsive React/TypeScript analytics dashboard with interval audit table, charts, cutoff controls and error messaging. Vite for the production build.
- `frontend/vercel.json`: same-origin `/api` rewrite to the separately deployed backend. SPA fallback.
- `backend/app/core.py`: UK local/UTC timestamps, actual and forecast retrieval, historical point-in-time selection, metrics.
- `backend/app/main.py`: HTTP API, request validation, controlled 502 upstream errors.
- `backend/index.py`: FastAPI serverless entrypoint for Vercel.
- `backend/tests/`: 11 deterministic tests for calculation, boundaries, valid data, API validation, mocked upstream errors.
- `backend/scripts/live_smoke.py`: live Elexon dataset contract test on GitHub Actions.
- `backend/scripts/deployment_smoke.py`: public frontend/backend/API health and real analysis test on GitHub Actions.
- `docker-compose.yml`: local frontend/backend container orchestration.
- `DEMO_SCRIPT.md`: required 10-minute customer and technical video outline.

## Local run

```bash
docker compose up --build
# Frontend http://localhost:5173
# FastAPI docs http://localhost:8000/docs
```

Or start independently:

```bash
cd backend
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
# another terminal:
cd frontend
npm install
npm run dev
```

Verify locally: `cd backend && python -m pytest -q`; `cd frontend && npm install && npm run build`.

## Deployment and verification

Two Vercel projects share the GitHub repo. The backend project root is `backend`, the frontend project root is `frontend`. The SPA proxies `/api` to the backend using its tracked `frontend/vercel.json` rewrite; no private API token is required.

GitHub Actions rebuilds and tests the application on push. External Elexon and deployed endpoint checks are independent of deterministic unit tests. Review their workflow results before stating production readiness.

## AI tools disclosure

OpenAI ChatGPT helped write the architecture, code, tests, documentation and deployment. A human should independently review the code and claims. Elexon BMRS data attribution and licence terms apply.
