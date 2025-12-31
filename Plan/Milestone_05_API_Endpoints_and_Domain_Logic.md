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
