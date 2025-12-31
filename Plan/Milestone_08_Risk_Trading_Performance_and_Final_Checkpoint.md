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
