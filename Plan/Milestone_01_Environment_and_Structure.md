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
