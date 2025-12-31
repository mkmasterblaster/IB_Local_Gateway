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
