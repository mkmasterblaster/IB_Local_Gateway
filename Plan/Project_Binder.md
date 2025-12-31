# Project Binder – Complete Implementation Plan

## Table of Contents
1. Master Implementation Plan
2. System Architecture Diagram
3. Milestones 1–8

## System Architecture Diagram
```

System Architecture Diagram
===========================

            +-------------------+
            |   React Web UI    |
            +---------+---------+
                      |
                      v
          +-----------+------------+
          |       FastAPI API      |
          | (Orders, Positions,    |
          |  Accounts, Metrics)    |
          +-----------+------------+
                      |
        +-------------+--------------+
        |     IBKR Client (ib_insync)|
        +-------------+--------------+
                      |
                      v
           +----------+-----------+
           |   IB Gateway (IBC)   |
           +-----------------------+

 Databases & Services:
 ---------------------
 PostgreSQL <----> FastAPI
 Redis     <----> FastAPI

 Monitoring:
 -----------
 Prometheus ---> FastAPI metrics
 Grafana    ---> Prometheus

```


# Master_Implementation_Plan.md

# IBKR Local API – Incremental Implementation Plan

This plan breaks the technical specification into **small, testable milestones**.  
Each milestone has:
- Clear goals
- Tasks and scope mapping back to the technical spec
- A **checkpoint** with a test plan
- A list of **planned unit tests** for every functionality/method added

Milestones:

1. Environment, Repo, and Project Structure  
2. Docker Compose, IB Gateway Container, and Configuration  
3. FastAPI Core App, Health Endpoint, and Base Logging  
4. IBKR Client Integration (ib_insync Wrapper)  
5. Trading API Endpoints and Domain Logic  
6. React Web UI  
7. Monitoring, Metrics, and Alerting  
8. Risk Management, Trading & Performance Hardening, Final Checkpoint  

See the individual `Milestone_XX_*.md` files for details.

The plan has been reviewed against the technical specification to ensure
coverage of:
- Purpose & Scope
- Core Components
- Hardware & OS Requirements
- Directory Layout
- Docker Compose & Configuration
- Metrics Collection (business + system)
- Development, Operational, Security, Trading, and Performance Best Practices
- Limitations

Nothing from the original specification is intentionally omitted; any new
details discovered during implementation should be appended to the relevant
milestone file.


---


# Milestone_01_Environment_and_Structure.md

# Milestone 1 – Environment, Repo, and Project Structure

## Goals
- Confirm macOS + Apple Silicon prerequisites for running IB Gateway via Docker.
- Create the base project structure described in the technical specification.
- Initialize version control, base documentation, and a shared logging/error-handling strategy.
- Establish initial unit test infrastructure.

## Scope Mapping to Technical Spec
- Section 1 – Purpose & Scope
- Section 3 – Hardware & OS Requirements
- Section 4 – Directory Layout
- Parts of Section 9 – Development Best Practices (code organization, testing strategy)

## Tasks

### 1. OS, Tooling, and Accounts
- Verify:
  - macOS Sequoia 15.6.1 running on Apple M2 Pro with 16 GB RAM.
  - Docker Desktop installed with support for `linux/amd64` images.
  - Docker Compose v2+ available (`docker compose version`).
- Confirm an **IBKR paper trading account** is active and credentials are available.
- Create/confirm a private Git repository for `local-ibkr-api`.

### 2. Create Base Directory Layout
- Create the directory structure:

  ```bash
  mkdir -p local-ibkr-api/services/stocks-api/app/{routers,models,schemas}
  mkdir -p local-ibkr-api/services/stocks-webapp/src/{components,pages}
  mkdir -p local-ibkr-api/monitoring/grafana/dashboards
  mkdir -p local-ibkr-api/nginx
  ```

- Add placeholder files:
  - `docker-compose.yml`
  - `services/stocks-api/Dockerfile`
  - `services/stocks-api/app/main.py`
  - `services/stocks-webapp/Dockerfile`
  - `monitoring/prometheus.yml`
  - `nginx/nginx.conf`
  - Root `README.md` (high-level summary).

### 3. Python & Node Environment
- Decide on global vs. container-only toolchains:
  - Python 3.11+ (inside containers).
  - Node.js (LTS) for React app builds.
- Create a base FastAPI `pyproject.toml` or `requirements.txt`:
  - `fastapi`, `uvicorn[standard]`, `pydantic`, `ib_insync`, `sqlalchemy`, `asyncpg`, `redis`, `prometheus_client`, `loguru` or `structlog`, `pytest`, `pytest-asyncio`.

### 4. Logging and Error-Handling Strategy (Cross-Cutting)
- Design a minimal logging standard (used in all milestones):
  - JSON-structured logs.
  - Levels: DEBUG, INFO, WARNING, ERROR.
  - Include correlation IDs / request IDs in logs where possible.
- Define a base error model for API responses:
  - `error_code`, `message`, `details`, `timestamp`.
- Define a global exception handler pattern for FastAPI (to be implemented in Milestone 3).

### 5. Testing Infrastructure
- Initialize `pytest` for `stocks-api`:
  - Create `services/stocks-api/tests/__init__.py`.
  - Add `pytest.ini` or `pyproject.toml` configuration.
- Add a minimal example test:

  ```python
  # services/stocks-api/tests/test_sanity.py
  def test_sanity():
      assert 1 + 1 == 2
  ```

- Plan unit test layout:
  - `tests/unit/` for pure functions & classes.
  - `tests/integration/` for DB/Redis/API tests.
  - `tests/e2e/` for end-to-end trading workflows (future milestones).

## Checkpoint – Milestone 1

### Definition of Done
- Project directory structure exactly matches the technical spec.
- Git repo initialized with `.gitignore` tuned for Python, Node, and Docker.
- Base FastAPI and test dependencies declared.
- Logging/error-handling strategy documented in `README.md`.

### Test Plan
- Run `pytest` in `services/stocks-api` and confirm all tests pass.
- Confirm Docker and Docker Compose versions:
  - `docker --version`
  - `docker compose version`
- Validate directory structure programmatically or with a checklist.

### Planned Unit Tests
- `test_sanity` (already present) as a CI canary.
- Once utility modules are added in later milestones, each helper/function will receive its own test under `tests/unit/`.

---


---


# Milestone_02_Docker_and_Configuration.md

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


---


# Milestone_03_FastAPI_Core_and_Health.md

# Milestone 3 – FastAPI Core App, Health Endpoint, and Base Logging

## Goals
- Implement the base FastAPI application with health endpoints.
- Integrate structured logging and global exception handling.
- Implement initial database and Redis connection wiring.
- Introduce Prometheus metrics scaffold.

## Scope Mapping to Technical Spec
- Section 1 – Purpose & Scope
- Section 2 – Core Components (FastAPI)
- Section 6 – Configuration & Secrets
- Section 8 – Metrics Collection (initial hooks)
- Section 9 – Development & Operational Best Practices

## Tasks

### 1. FastAPI `main.py`
- Implement an application factory pattern:
  - Creates FastAPI app.
  - Mounts routers (health, status).
  - Adds middleware for:
    - Request/response logging.
    - Correlation ID injection.
    - Exception handling.

- Add `/health` endpoint:
  - Returns:
    - `status: "ok"` or `"degraded"`
    - `ib_gateway_connected: bool` (temporary stub)
    - `db_connected: bool`
    - `redis_connected: bool`

### 2. Configuration and Dependency Injection
- Implement a `config.py` module:
  - Reads env vars for DB, Redis, IB host/ports, JWT secret, environment.
  - Provides Pydantic `Settings` class.

- Implement dependency providers:
  - `get_db_session()`
  - `get_redis_client()`

### 3. Logging and Error Handling
- Implement central logging setup:
  - Configure JSON logs with timestamp, level, logger name, and request ID.
  - Add FastAPI exception handlers for:
    - `HTTPException`
    - Validation errors (`RequestValidationError`)
    - Unhandled exceptions.

- Use structured log messages for:
  - Request start/end.
  - Errors with stack traces.

### 4. Prometheus Metrics Scaffold
- Integrate `prometheus_client`:
  - Create `REQUEST_COUNT`, `REQUEST_LATENCY` histograms/counters.
  - Middleware to record:
    - method, path, status_code, latency.
- Expose `/metrics` endpoint for Prometheus scraping.

## Checkpoint – Milestone 3

### Definition of Done
- FastAPI app runs inside `stocks-fastapi` container.
- `/health` and `/metrics` endpoints respond successfully.
- Logs appear in JSON format, include request IDs.
- DB and Redis connectivity checked in `/health` (or flagged as degraded).

### Test Plan
- `curl` or browser:
  - `GET /health` → `200 OK`, structured JSON body.
  - `GET /metrics` → Prometheus text output.
- Docker logs:
  - Confirm request and error logs.

### Planned Unit Tests
- `tests/unit/test_config.py`:
  - Verify `Settings` loads env values and defaults.

- `tests/unit/test_health_router.py`:
  - Test `/health` response structure (using FastAPI TestClient).
  - Simulate:
    - healthy DB/Redis.
    - failing DB/Redis.

- `tests/unit/test_logging_middleware.py`:
  - Ensure middleware runs and returns proper response status.
  - Confirm log entries include the expected fields (using a log handler stub).

---


---


# Milestone_04_IBKR_Client_Integration.md

# Milestone 4 – IBKR Client Integration (ib_insync Wrapper)

## Goals
- Implement a dedicated IBKR client wrapper for IB Gateway using `ib_insync`.
- Handle connection lifecycle, reconnect logic, basic market data, and simple orders.
- Add logging and error handling around IBKR operations.
- Provide mocks to allow unit testing without a live gateway.

## Scope Mapping to Technical Spec
- Section 2 – Core Components (IB Gateway, FastAPI)
- Section 5 – Docker Compose (IB Gateway networking)
- Section 6 – Configuration & Secrets
- Section 8 – Metrics Collection (IB connection status)
- Section 9 – Trading & Performance Best Practices

## Tasks

### 1. IBKR Client Class
- Add `ib_client.py` with `IBKRClient` class:
  - Responsibilities:
    - Connect to IB Gateway (host, port, clientId).
    - Track connection status.
    - Provide methods:
      - `connect()`, `disconnect()`
      - `is_connected()`
      - `place_order(contract, order)`
      - `request_market_data(contract)`
      - `cancel_market_data(contract)`

- Use robust logging for:
  - Connection attempts and failures.
  - Order submissions and responses.
  - Market data subscription changes.

### 2. Reconnection Logic and Error Handling
- Implement retry/backoff on connection failure.
- Convert IBKR exceptions to internal error codes.
- Ensure that methods return typed results or raise well-defined application exceptions.

### 3. Prometheus Metrics
- Add gauges/counters:
  - `ib_connection_status` (0/1).
  - `ib_orders_total`.
  - `ib_order_errors_total`.
  - `ib_market_data_subscriptions`.

### 4. Mocks and Testability
- Define an `IBKRClientProtocol` or interface.
- Implement a `MockIBKRClient` for unit tests:
  - Fake order IDs, fills, and connection states.
- Inject client via FastAPI dependencies for easy swapping between real and mock.

## Checkpoint – Milestone 4

### Definition of Done
- `IBKRClient` can connect to a **paper** IB Gateway when running full stack.
- Simple round-trip:
  - Request market data for a known symbol (e.g. AAPL).
  - Place a tiny paper trade (e.g. 1 share).
- Logs and metrics show connection status and order events.

### Test Plan
- Live (paper) tests:
  - Start full Docker stack.
  - Use an internal script or temporary endpoint to:
    - Connect to IB.
    - Place and cancel a test order.
- Observability:
  - Check logs for connect/disconnect, order placement.
  - Check Prometheus metrics for `ib_connection_status`.

### Planned Unit Tests
- `tests/unit/test_ib_client.py`:
  - Test `connect`/`disconnect` with mocked ib_insync.
  - Test behavior when gateway is unavailable (exceptions, retries).
  - Test `place_order` happy path and failure path.
- `tests/unit/test_mock_ib_client.py`:
  - Ensure mock client implements protocol and returns deterministic results.

---


---


# Milestone_05_API_Endpoints_and_Domain_Logic.md

# Milestone 5 – Trading API Endpoints and Domain Logic

## Goals
- Implement main FastAPI trading endpoints for orders, positions, and account info.
- Add domain models and Pydantic schemas.
- Integrate risk checks and validation (pre-trade).
- Ensure each endpoint is fully tested with unit and integration tests.

## Scope Mapping to Technical Spec
- Section 2 – Core Components (stocks-fastapi)
- Sections 8 & 9 – Business metrics, development and trading best practices

## Tasks

### 1. Data Models and Schemas
- SQLAlchemy models for:
  - Orders
  - Fills
  - Positions snapshots
  - Accounts and PnL snapshots

- Pydantic schemas:
  - `OrderRequest`, `OrderResponse`
  - `Position`, `AccountSummary`
  - `ErrorResponse`

### 2. Router Implementation
- `/orders`:
  - `POST /orders` – place order (market, limit; more types later).
  - `GET /orders` – list orders.
  - `GET /orders/{order_id}` – detailed status.

- `/positions`:
  - `GET /positions` – current open positions.

- `/accounts`:
  - `GET /accounts/{account_id}/pnl`
  - `GET /accounts/{account_id}/summary`

- Add risk checks:
  - Validate notional size against limits.
  - Ensure symbol is allowed.
  - Enforce max leverage (if applicable).

### 3. Logging and Error Handling
- Log each inbound order request and final IBKR result.
- Log risk-check failures as WARN (not ERROR).
- Convert IBKR errors to clean `ErrorResponse` with `error_code`.

### 4. Metrics
- Business metrics:
  - `orders_total` (by type).
  - `order_latency_seconds`.
  - `active_positions_total`.
  - `pnl_unrealized_total`.

## Checkpoint – Milestone 5

### Definition of Done
- Endpoints implemented and surfaced in `/docs` (Swagger UI).
- Orders can be placed to IBKR paper and recorded in Postgres.
- Positions and account info endpoints return meaningful data.

### Test Plan
- Use FastAPI TestClient to:
  - POST a sample order and inspect the response.
  - GET orders and positions list.
- Integration tests using `MockIBKRClient`:
  - Validate that DB entries are created correctly.
  - Validate failure paths.

### Planned Unit Tests
- `tests/unit/test_orders_router.py`
  - Validation of incoming `OrderRequest`.
  - Risk-check failures.
- `tests/unit/test_positions_router.py`
- `tests/unit/test_accounts_router.py`
- `tests/integration/test_orders_ib_mock.py`
  - End-to-end order flow with mock IB client and real DB.

---


---


# Milestone_06_React_WebUI.md

# Milestone 6 – React Web UI

## Goals
- Implement a React UI that interacts with the FastAPI backend.
- Provide pages for dashboard, positions, orders, and basic monitoring.
- Incorporate client-side validation, error display, and logging hooks.

## Scope Mapping to Technical Spec
- Section 2 – Core Components (stocks-webapp)
- Section 4 – Directory Layout
- Section 9 – Development and Trading Best Practices (user-facing workflows)

## Tasks

### 1. React App Skeleton
- Initialize React app inside `services/stocks-webapp`.
- Configure `REACT_APP_API_URL` and `REACT_APP_CONTAINER_TYPE=stocks`.

### 2. Pages and Components
- `DashboardPage`:
  - High-level account value, open PnL, and recent activity.

- `OrdersPage`:
  - New order ticket form.
  - Order history table.

- `PositionsPage`:
  - Open positions table.
  - Basic filtering and sorting.

### 3. API Client and Error Handling
- Implement a small API client wrapper:
  - Centralizes base URL and headers.
  - Handles JSON parsing and error translation.

- Global error boundary:
  - Displays user-friendly messages.
  - Logs details to console (and optionally to backend later).

### 4. UI Tests
- Use Jest + React Testing Library:
  - Test rendering of pages.
  - Test validation behavior for order form.
  - Test that API calls are made correctly (mock fetch/axios).

## Checkpoint – Milestone 6

### Definition of Done
- Frontend can:
  - Fetch positions and orders from backend.
  - Place a simple market/limit order via UI.
- Basic error messages shown for failure cases.

### Test Plan
- Manual E2E test:
  - Start full stack.
  - Open `http://localhost:3001`.
  - Place a test paper order; confirm in:
    - UI
    - DB
    - IBKR TWS / Account.

### Planned Unit Tests
- `src/__tests__/DashboardPage.test.tsx`
- `src/__tests__/OrdersPage.test.tsx`
- `src/__tests__/PositionsPage.test.tsx`
- API client tests for success and failure paths.

---


---


# Milestone_07_Monitoring_Metrics_and_Alerting.md

# Milestone 7 – Monitoring, Metrics, and Alerting

## Goals
- Fully instrument the system with Prometheus metrics.
- Add Grafana dashboards for system, trading, and business metrics.
- Design alerting rules for critical and warning situations.

## Scope Mapping to Technical Spec
- Section 8 – Metrics Collection
- Section 9 – Operational and Performance Best Practices

## Tasks

### 1. Prometheus Setup
- Configure `monitoring/prometheus.yml`:
  - Scrape `stocks-fastapi:8000` for `/metrics`.
  - Scrape other services if needed (custom exporters).

### 2. Metrics Implementation
- System metrics:
  - `api_requests_total`
  - `api_request_duration_seconds`
  - `ib_connection_status`

- Business metrics:
  - `orders_total`
  - `order_latency_seconds`
  - `active_positions_total`
  - `pnl_unrealized_total`

### 3. Grafana Dashboards
- Create dashboards for:
  - API performance.
  - Gateway connection stability.
  - Order volumes and rejection rates.
  - CPU/memory/disk (via node exporter if desired).

### 4. Alerting Rules
- Critical Alerts
  - IB Gateway connection loss.
  - Database connection failure.
  - High order rejection rate.
  - Position limit breaches.
  - Unusual P&L moves.

- Warning Alerts
  - High API latency.
  - Low disk space.
  - Memory > 80%.
  - Failed authentication attempts.
  - Market data feed delays.

## Checkpoint – Milestone 7

### Definition of Done
- Prometheus successfully scrapes metrics.
- Grafana dashboards display real-time data.
- Prototype alerting rules defined (even if using local alertmanager or manual review).

### Test Plan
- Force test conditions:
  - Stop IB Gateway → verify `ib_connection_status` drops and chart reflects it.
  - Generate load → inspect request latency histograms.
- Validate metric labels for correctness and consistency.

### Planned Unit Tests
- Tests around metric helper functions:
  - Ensure helper wraps increments and observations correctly.
- Tests to verify `/metrics` endpoint remains functional under load (integration).

---


---


# Milestone_08_Risk_Trading_Performance_and_Final_Checkpoint.md

# Milestone 8 – Risk Management, Trading & Performance Hardening, Final Checkpoint

## Goals
- Implement trading risk management controls.
- Add performance optimizations (connection pooling, caching, async operations).
- Validate limitations and behaviors from the technical spec.
- Run full end-to-end test plans and finalize documentation.

## Scope Mapping to Technical Spec
- Section 9 – Trading, Operational, Performance & Security Best Practices
- Section 10 – Limitations

## Tasks

### 1. Risk Management Features
- Implement:
  - Stop-loss order support (or synthetic stop-loss logic).
  - Circuit breaker:
    - Halt trading if account P&L drops beyond threshold.
    - Halt trading on repeated order rejections.

- Add pre-trade compliance checks:
  - Position and notional limits.
  - Instrument whitelist/blacklist.

### 2. Performance Optimizations
- API optimization:
  - Connection pooling for DB.
  - Efficient use of the IBKR client (reuse, not reconnect per request).
  - Async endpoints where beneficial.

- DB optimization:
  - Add indexes for hot queries (orders by time, symbol, status).
  - Implement archival strategy for old data.

### 3. Security Hardening
- Confirm:
  - No secrets in logs.
  - `ENVIRONMENT` controls debug/trace behavior.
  - JWT auth and roles (admin/trader/viewer) are enforced.

### 4. Limitations Validation
- Validate practical impact of:
  - IBKR 50 msg/sec and pacing rules.
  - Daily restart behavior of IB Gateway.
  - Memory and CPU usage of containers.

## Final Checkpoint – Milestone 8

### Definition of Done
- System is stable for day-long paper trading sessions.
- Risk controls and circuit breakers function as intended.
- Monitoring and logging provide enough visibility to diagnose issues.

### Final Test Plan
- End-to-end trading simulation:
  - Place a batch of orders (various types).
  - Simulate adverse P&L to trigger risk limits.
  - Confirm behavior under partial failures (e.g., DB temporarily unavailable).

- Run:
  - Full unit test suite (`pytest` for API, Jest for webapp).
  - Integration tests with mock IB client.
  - Selective paper tests against real IB Gateway.

### Planned Unit Tests
- Additional tests for:
  - Risk-check functions (max loss, max size).
  - Circuit breaker behavior.
  - Performance helper functions (caching, batching).

---


---
