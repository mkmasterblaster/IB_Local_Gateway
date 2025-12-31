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
