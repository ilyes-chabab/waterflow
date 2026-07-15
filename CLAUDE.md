# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Waterflow 2 is an MLOps platform that predicts water **potability** (potable/non potable) from 9
physico-chemical measurements (ph, hardness, solids, chloramines, sulfate, conductivity,
organic_carbon, trihalomethanes, turbidity), using an XGBoost model tracked and served through
MLflow's Model Registry. It exposes a FastAPI backend, a Streamlit UI, and OCR-based ingestion of
lab report images/PDFs.

## Running the stack

### Option A — Docker Compose (recommended, all services orchestrated together)

```bash
docker compose up --build
```

Starts `mlflow` (:5000), `api` (:8000), `streamlit` (:8501), `prometheus` (:9090) and `grafana`
(:3000). The `mlflow` service persists its registry/artifacts to `./mlflow_data` (bind-mounted) —
without it the container's own SQLite backend store (`mlflow.db`, created in the container's
working dir when no `--backend-store-uri` is passed) would be lost on every rebuild. The `api`
service reads `MLFLOW_TRACKING_URI` (defaults to `http://127.0.0.1:5000`, overridden to
`http://mlflow:5000` in `docker-compose.yml`) and persists `data/db/waterflow.db` via a bind mount.

On a fresh `mlflow_data/` (first run, or after deleting it), the model registry is empty and
`/api/measurements` returns `503` until a model is trained and promoted:

```bash
python scripts/experiment.py   # points at http://127.0.0.1:5000, mapped from the mlflow container
docker compose restart api     # reload the newly-registered "Production" model
```

### Option B — run services individually (no Docker)

```bash
# 1. MLflow tracking server + model registry (UI at http://127.0.0.1:5000)
python -m mlflow server --host 127.0.0.1 --port 5000

# 2. FastAPI backend (loads the "Production" stage of water_quality_model from MLflow at startup)
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# 3. Streamlit UI (http://localhost:8501), talks to the API at 127.0.0.1:8000
python -m streamlit run ui.py
```

`waterflow2.bat` runs the same three commands as Option B, in order, on Windows.

First-time setup: create the first Admin API key with `python scripts/init_admin.py` (prints the
plain-text key once — it's only ever stored as a SHA-256 hash in the DB).

Training a new model version: `python scripts/experiment.py` (loads
`data/processed/processed_data.pkl`, applies SMOTE, trains XGBoost, logs params/metrics/model to
MLflow, registers it as `water_quality_model`, and transitions the newest version to the
`Production` stage — this immediately affects what the running API serves next time it (re)loads
the model).

## Tests

```bash
pytest
```

`pytest.ini` restricts discovery to `tests/`. `tests/test_pipeline.py` covers the FastAPI app
directly (via `fastapi.testclient.TestClient`, fixtures in `tests/conftest.py` mock MLflow/OCR so
no external services are required); `tests/test_ui_integration.py` covers the Streamlit pages
(`views/*.py`, `dashboard_qualite.py`) via `streamlit.testing.v1.AppTest`, bridged to the same
`TestClient` so UI code exercises the real API routes. See `tests/test_README.md` for setup/
coverage commands and `tests/bugTrouvé_README.md` for a log of real bugs found and fixed while
building this suite.

## Architecture

- **`api/main.py`** — FastAPI app. Loads the MLflow `Production` model once at startup
  (`lifespan`), and applies a fixed decision threshold (`app.state.best_threshold`, currently
  0.37) to `predict_proba` output rather than the model's default 0.5 cutoff. Middleware stack:
  `metrics_middleware` (Prometheus RED metrics, exposed on `GET /metrics`), `security_headers`
  (X-Content-Type-Options/X-Frame-Options/Referrer-Policy), `access_log` (writes every request to
  the `audit_logs` table, resolving the requesting user by re-hashing the `X-API-Key` header).
  `/api/login` and `/api/measurements` are rate-limited (`slowapi`).
- **`api/auth.py`** — shared `get_current_user` / `require_role(*roles)` FastAPI dependencies used
  by both `api/main.py` and `api/ocr_router.py`. Auth is API-key based (`X-API-Key` header,
  SHA-256 hashed, looked up in the `users` table); roles are `Client`, `Quality_Analyst`, `Admin`.
  Only the Admin role can create/list clients, rotate keys, or read audit logs; Quality_Analyst and
  Admin can hit the `/api/dashboard/*` routes.
- **`api/ocr_router.py`** — `/api/ocr/lab-report` sends an uploaded image/PDF to the OCR.space API,
  regex-parses the returned text for the same 9 features (plus a few extra fields like nitrates),
  and runs the same prediction path as `/api/measurements`. The client_id always comes from the
  authenticated API key, never from OCR/user input (deliberate RGPD-safety choice). OCR failures
  (timeout/unreachable/HTTP/processing errors) are logged structurally and counted in the
  `ocr_failures_total` Prometheus metric, and degrade gracefully (proper HTTP error code) instead
  of crashing the app.
- **`api/logging_config.py`** — structured JSON logging (`logger` from `waterflow2` logger), used
  in place of `print()` throughout `api/`. Each log line is one JSON event with context via
  `extra={...}`, filterable/aggregatable during incident diagnosis (see `docs/incidents/`).
- **`data/db/WaterFlowDB.py`** — the only data-access layer, wrapping a single SQLite file at
  `data/db/waterflow.db` (gitignored — real API-key hashes + audit logs, never versioned). Tables:
  `users` (api_key stored as SHA-256 hash, `right` = role, `is_active` supports key revocation),
  `prediction` (one row per measurement + potability result + `source`: `manuel` or `ocr`),
  `audit_logs`. `_ensure_prediction_columns()` runs a soft migration (adds
  columns if missing) on every connect — there is no separate migration tool. Every route
  opens/closes its own `WaterFlowDB()` connection rather than sharing one.
- **`scripts/experiment.py`** — standalone MLflow training script (not imported by the API): loads
  preprocessed train/val split, balances classes with SMOTE, trains XGBoost, sweeps thresholds
  0.30–0.70 for best F1, logs everything to the `experiment_water_quality` MLflow experiment, and
  registers + promotes the model to `Production`. The threshold found here must be manually kept in
  sync with `app.state.best_threshold` in `api/main.py`.
- **`scripts/validate_data.py`**, **`scripts/validate_model.py`** — CI gates (`.github/workflows/ci.yml`):
  schema/missing-value check on the raw CSV, and a non-MLflow retrain + F1-score threshold check.
- **`scripts/compute_means.py`**, **`scripts/init_admin.py`**, **`scripts/pile.py`** — one-off/setup
  scripts. `pile.py` is an early local-OCR (pytesseract) prototype, superseded by
  `api/ocr_router.py`'s OCR.space-based implementation; kept for reference, not used by the app.
- **`ui.py` + `views/`** — Streamlit multi-page app. Role read out of the API's `/api/login`
  response drives which pages (`st.navigation`) are shown: `Admin` gets
  `views/accueil_admin.py` + `views/securite_admin.py`; `Quality_Analyst` gets
  `dashboard_qualite.py`; `Client` gets `views/panel_test.py`, `views/historique.py`, and
  `views/mes_donnees.py` (RGPD self-service: `GET`/`DELETE /api/me`). Session state
  (`st.session_state`) holds the API key and is sent as `X-API-Key` on every backend call — there's
  no server-side session. `API_BASE_URL` (all `ui.py`/`views/*.py`/`dashboard_qualite.py`) and
  `MLFLOW_TRACKING_URI` (`api/main.py`) are both overridable via environment variables, defaulting
  to `127.0.0.1` for non-Docker use and overridden to Docker Compose service names in
  `docker-compose.yml`.
- **`data/`** — `raw/` has the source Kaggle-style CSV; `processed/` has the pickled
  train/val/test split consumed by `scripts/experiment.py`; `description/` and `output/` hold notes
  and EDA plots from the notebooks in `notebooks/`.
- **`notebooks/`** — only actual Jupyter notebooks (`data-analysis.ipynb`,
  `water_quality_analysis.ipynb`). Specs/design docs live in `docs/` (see below).
- **`docs/`** — `user_stories.md` (functional specs, WCAG criteria per story), `parcours_utilisateurs.md`
  (Mermaid user-journey flowcharts), `checklist_C9_C19.md` (RNCP audit checklist),
  `Slidesupport/MCD.txt` + `Slidesupport/MPD.txt` (data model, Merise formalism),
  `ACCESSIBILITE_DOCUMENTATION.md` (accessibility of the documentation format itself),
  `incidents/` (incident report template + real incident write-ups, DDCR format).

## Conventions to preserve

- API responses and in-code comments are in French; keep new endpoints/docstrings consistent with
  that style (see the `tags=[...]` groupings in `api/main.py`: Auth, Prélèvements, Clients, RGPD,
  Dashboard, Admin).
- API keys are only ever returned in plaintext once (on creation or key rotation) — never re-log or
  persist the plaintext value anywhere else.
- RGPD endpoints (`/api/me` GET/DELETE) matter to this project: account deletion anonymizes
  `audit_logs.user_id` to NULL instead of deleting audit rows, while actually deleting the user's
  `prediction` rows. Exposed in the UI via `views/mes_donnees.py`.
- Relative file paths in code (`data/processed/...`, `data/db/waterflow.db`, `mean_features.json`)
  are resolved against the current working directory, not the script's location — always run
  scripts from the repo root. Never hardcode Windows-style backslash paths (breaks on Linux/Docker).
