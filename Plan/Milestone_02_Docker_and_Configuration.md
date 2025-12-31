# Milestone 2 – Docker Compose, IB Gateway Container, and Configuration

## Goals
- Implement Docker Compose stack with IB Gateway, Postgres, Redis, FastAPI, and webapp skeleton services.
- Correctly configure `platform: linux/amd64` for IB Gateway on Apple Silicon.
- Configure environment via `.env` including IBKR credentials and app secrets.
- Verify basic container lifecycle and health for non-IB services.

## Scope Mapping to Technical Spec
- Section 3 – Hardware & OS Requirements
- Section 4 – Directory Layout
- Section 5 – Docker Compose – Local Integration
- Section 6 – Configuration & Secrets
- Parts of Section 9 – Operational Best Practices (container management, resource limits later).

## Tasks

### 1. Create `.env` File
- In `local-ibkr-api/.env`:

  ```env
  STOCKS_TWS_USERID=your_ibkr_username
  STOCKS_TWS_PASSWORD=your_ibkr_password_or_ibc_macro
  STOCKS_TRADING_MODE=paper
  STOCKS_JWT_SECRET=super_long_random_secret
  ENVIRONMENT=development
  ```

- Ensure `.gitignore` includes `.env`.

### 2. Implement Full `docker-compose.yml`
- Include all core services with details, volumes, and healthchecks:

  - `stocks-ib-gateway`  
    - `platform: linux/amd64`  
    - `volumes: stocks-settings, stocks-logs`  
    - `healthcheck` (pgrep `ibgateway`)  
    - Ports: `5001`, `5002`, `5900` bound to localhost.

  - `postgres`  
    - `volumes: stocks-db-data:/var/lib/postgresql/data`  
    - Expose local dev port 5433.

  - `redis`  
    - Expose local dev port 6380.

  - `stocks-fastapi`  
    - Build from `services/stocks-api/Dockerfile`  
    - Environment variables for DB, Redis, IB Gateway host/port  
    - `volumes: stocks-api-logs:/app/logs`.

  - `stocks-webapp`  
    - Build from `services/stocks-webapp/Dockerfile`  
    - `container_name: stocks-webapp`  
    - `REACT_APP_API_URL` and `REACT_APP_CONTAINER_TYPE=stocks`.

  - Volume definitions:

    ```yaml
    volumes:
      stocks-settings:
      stocks-logs:
      stocks-api-logs:
      stocks-db-data:
    ```

### 3. Minimal Dockerfiles for API and Webapp
- API Dockerfile:
  - Base Python image
  - Install dependencies
  - Expose port 8000
  - Entrypoint: `uvicorn app.main:app --host 0.0.0.0 --port 8000`

- Webapp Dockerfile:
  - Node LTS base
  - Install dependencies and build React app
  - Use dev server or Nginx static assets for now.

### 4. IB Gateway / IBC Specifics
- Configure environment for IB Gateway container:
  - `TRADING_MODE=paper`
  - `TIME_ZONE=America/New_York`
  - `AUTO_RESTART_TIME="01:00"`
- Confirm IBKR paper account login process (manual first using VNC, then automated in later milestones).

### 5. Logging and Error Handling
- Ensure `stocks-fastapi` and `stocks-webapp` Dockerfiles:
  - Write logs to `/app/logs` (for API).
  - Log to stdout/stderr as primary sink (for container log collection).
- Define Docker logging driver and options if needed (e.g., json-file with size limits).

## Checkpoint – Milestone 2

### Definition of Done
- `docker compose up --build` starts all services without crash.
- Non-IB services (`postgres`, `redis`, `stocks-fastapi`, `stocks-webapp`) stay healthy.
- IB Gateway container runs and healthcheck passes once Gateway fully boots.

### Test Plan
- Run `docker compose ps` to verify all containers are `running`.
- Use `docker compose logs` to verify:
  - No crash loops.
  - Env variables resolved.
  - Logs written correctly.
- Database connectivity dry-run:
  - From `stocks-fastapi` container, run a simple DB connection script.
- Redis connectivity dry-run:
  - From `stocks-fastapi` container, ping Redis.

### Planned Unit Tests
- Add `tests/unit/test_config.py`:
  - Test environment variable loading logic.
  - Test that configuration objects derive IB host/ports/db URLs correctly.
- Add `tests/unit/test_logging_setup.py`:
  - Verify logging configuration (handlers, formats) builds without errors.

---
