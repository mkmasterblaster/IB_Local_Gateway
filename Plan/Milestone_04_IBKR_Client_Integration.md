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
