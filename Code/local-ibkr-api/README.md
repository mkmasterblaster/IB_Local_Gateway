# Local IBKR API Integration

A comprehensive local trading development environment integrating Interactive Brokers Gateway with FastAPI backend, React frontend, and full observability stack.

## 🎯 Project Overview

This system provides a single-developer environment for paper trading that mirrors production architecture:

- **IB Gateway**: Headless IBKR API connectivity with automated login and 2FA
- **FastAPI Backend**: REST + WebSocket endpoints for order management
- **React Frontend**: Modern trading UI
- **PostgreSQL**: Persistent storage for orders, fills, and trade logs
- **Redis**: Real-time pub/sub and caching layer
- **Prometheus + Grafana**: Comprehensive metrics and dashboards

## 🏗️ Architecture

```
React UI (port 3001)
    ↓
FastAPI API (port 8000)
    ↓
IBKR Client (ib_insync)
    ↓
IB Gateway (ports 5001/5002)

Data: PostgreSQL (5433) + Redis (6380)
Monitoring: Prometheus + Grafana
```

## 💻 System Requirements

- **OS**: macOS Sequoia 15.6.1 (or compatible)
- **Hardware**: Apple M2 Pro (or similar), 16GB RAM
- **Docker**: Docker Desktop with Rosetta/QEMU for linux/amd64 images
- **Docker Compose**: v2+
- **Python**: 3.12
- **Node.js**: LTS (for React builds)

## 📁 Project Structure

```
local-ibkr-api/
├── docker-compose.yml          # Orchestration for all services
├── .env                        # Environment variables (NOT in git)
├── services/
│   ├── stocks-api/            # FastAPI backend
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── pyproject.toml
│   │   ├── app/
│   │   │   ├── main.py        # FastAPI application
│   │   │   ├── config.py      # Configuration management
│   │   │   ├── ib_client.py   # IBKR client wrapper
│   │   │   ├── routers/       # API endpoints
│   │   │   ├── models/        # SQLAlchemy models
│   │   │   ├── schemas/       # Pydantic schemas
│   │   │   └── utils/         # Helper functions
│   │   └── tests/
│   │       ├── unit/          # Unit tests
│   │       ├── integration/   # Integration tests
│   │       └── e2e/           # End-to-end tests
│   └── stocks-webapp/         # React frontend
│       ├── Dockerfile
│       ├── package.json
│       └── src/
│           ├── components/    # React components
│           ├── pages/         # Page components
│           └── utils/         # Utility functions
├── monitoring/
│   ├── prometheus/
│   │   └── prometheus.yml     # Prometheus config
│   └── grafana/
│       └── dashboards/        # JSON dashboard definitions
└── nginx/
    └── nginx.conf             # Reverse proxy config
```

## 📝 Logging Strategy

### Structured Logging Standards

All services use **JSON-structured logs** with the following standards:

#### Log Levels
- `DEBUG`: Detailed diagnostic information
- `INFO`: General informational messages
- `WARNING`: Warning messages for recoverable issues
- `ERROR`: Error events that might still allow the application to continue

#### Required Fields
Every log entry includes:
```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "INFO",
  "logger": "app.main",
  "message": "Request processed successfully",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "correlation_id": "parent-trace-id"
}
```

#### Context Fields
Additional fields based on context:
- **API Requests**: `method`, `path`, `status_code`, `latency_ms`, `user_id`
- **Trading Operations**: `order_id`, `symbol`, `quantity`, `order_type`, `account_id`
- **IBKR Events**: `ib_event_type`, `ib_error_code`, `connection_status`
- **Errors**: `error_code`, `error_type`, `stack_trace`, `details`

### Implementation

#### Python (structlog)
```python
import structlog

logger = structlog.get_logger()

logger.info(
    "order_placed",
    order_id=order.id,
    symbol=order.symbol,
    quantity=order.quantity,
    order_type=order.type
)
```

#### Correlation IDs
- Generated per request in FastAPI middleware
- Propagated through all downstream operations
- Included in all log entries
- Returned in response headers as `X-Request-ID`

### Log Destinations
- **Development**: stdout/stderr (captured by Docker logs)
- **Files**: `/app/logs/` directory (mounted volume)
- **Aggregation**: Ready for ELK/Loki integration (future)

## ⚠️ Error Handling Strategy

### Error Response Model

All API errors return consistent JSON structure:

```json
{
  "error_code": "ORDER_VALIDATION_FAILED",
  "message": "Order quantity exceeds position limit",
  "details": {
    "field": "quantity",
    "limit": 1000,
    "requested": 1500
  },
  "timestamp": "2024-01-15T10:30:00.123Z",
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Error Code Categories

#### Client Errors (4xx)
- `VALIDATION_ERROR`: Input validation failed
- `AUTHENTICATION_REQUIRED`: Missing or invalid authentication
- `AUTHORIZATION_FAILED`: Insufficient permissions
- `RESOURCE_NOT_FOUND`: Requested resource doesn't exist
- `RATE_LIMIT_EXCEEDED`: Too many requests

#### Business Logic Errors
- `ORDER_VALIDATION_FAILED`: Order fails pre-trade checks
- `INSUFFICIENT_FUNDS`: Account lacks required capital
- `POSITION_LIMIT_EXCEEDED`: Position size limits breached
- `SYMBOL_NOT_ALLOWED`: Trading not permitted for symbol
- `MARKET_CLOSED`: Operation not allowed outside market hours

#### Server Errors (5xx)
- `INTERNAL_SERVER_ERROR`: Unexpected server error
- `IB_CONNECTION_FAILED`: Cannot connect to IB Gateway
- `DATABASE_ERROR`: Database operation failed
- `EXTERNAL_SERVICE_ERROR`: Third-party service unavailable

#### IBKR-Specific Errors
- `IB_INVALID_CONTRACT`: Contract specification invalid
- `IB_ORDER_REJECTED`: IBKR rejected the order
- `IB_MARKET_DATA_ERROR`: Market data subscription failed
- `IB_AUTHENTICATION_FAILED`: IBKR authentication failed

### Global Exception Handlers

FastAPI application implements global handlers for:

1. **HTTPException**: Convert to error response model
2. **RequestValidationError**: Pydantic validation failures
3. **SQLAlchemyError**: Database errors
4. **IBKRError**: IBKR-specific exceptions
5. **Exception**: Catch-all for unexpected errors

### Exception Handler Example

```python
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": determine_error_code(exc),
            "message": exc.detail,
            "details": {},
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request.state.request_id
        }
    )
```

## 🧪 Testing Strategy

### Test Organization

```
tests/
├── unit/              # Fast, isolated tests
│   ├── test_config.py
│   ├── test_schemas.py
│   └── test_utils.py
├── integration/       # Tests with DB/Redis/IBKR
│   ├── test_orders_flow.py
│   └── test_ib_client.py
└── e2e/              # Full end-to-end scenarios
    └── test_trading_workflow.py
```

### Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# With coverage
pytest --cov=app --cov-report=html

# Specific test
pytest tests/unit/test_config.py -v
```

### Test Requirements
- Minimum 80% code coverage
- All public APIs must have tests
- Critical trading logic requires unit + integration tests
- Mock IBKR client for unit tests

## 🚀 Quick Start

```bash
# 1. Clone repository
git clone <repo-url>
cd local-ibkr-api

# 2. Create .env file with your credentials
cp .env.example .env
# Edit .env with your IBKR credentials

# 3. Build and start services
docker compose up --build

# 4. Verify services
docker compose ps

# 5. Check health
curl http://localhost:8000/health

# 6. Access UI
open http://localhost:3001
```

## 📊 Monitoring & Metrics

### Prometheus Metrics
- **System**: Request rates, latencies, error rates
- **Business**: Orders placed, positions, P&L
- **IBKR**: Connection status, API errors

### Grafana Dashboards
- API Performance
- Trading Activity
- System Health
- IBKR Gateway Status

Access: http://localhost:3000 (default Grafana port)

## 🔐 Security Notes

- **Never commit `.env` files**
- **Rotate IBKR credentials regularly**
- **Use paper trading account for development**
- **JWT secrets must be strong and unique**
- **Review logs for sensitive data before sharing**

## 🐛 Troubleshooting

### IB Gateway won't connect
- Check IBKR credentials in `.env`
- Verify paper trading is enabled
- Check VNC on port 5900 to see Gateway UI
- Review Gateway logs: `docker logs stocks-ib-gateway`

### API won't start
- Check logs: `docker logs stocks-fastapi`
- Verify DB connection
- Ensure port 8000 is available

### Tests fail
- Ensure test database is clean
- Check mock configurations
- Review test fixtures

## 📚 Additional Resources

- [Interactive Brokers API](https://interactivebrokers.github.io/)
- [ib_insync Documentation](https://ib-insync.readthedocs.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Technical Specification](./docs/IBKR_Local_API_Complete.md)

## 📄 License

Private - For Development Use Only

## 🤝 Contributing

This is a single-developer environment. For questions or issues, contact the project maintainer.

---

**Status**: Milestone 01 Complete ✅
**Last Updated**: 2024-12-10
