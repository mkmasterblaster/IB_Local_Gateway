
# Technical Specification – Local IBKR API Integration (Complete Edition)
macOS Sequoia 15.6.1 – MacBook Pro M2 Pro (16GB)  
Paper Trading Environment

---

## 1. Purpose & Scope
Integrate IB Gateway, FastAPI backend, React web UI, PostgreSQL, Redis,  
Nginx, and Prometheus/Grafana into a unified local trading development  
environment using Docker Compose on macOS.

The target is a single-developer environment that mirrors future production.

---

## 2. Core Components

### • IB Gateway (gnzsnz/ib-gateway-docker)
- Headless API connectivity
- Automated login, 2FA handling, restarts via IBC

### • stocks-fastapi
- IBKR socket API client  
- REST + WebSocket endpoints  
- Order management and account functions  

### • stocks-webapp
- React-based trading UI  

### • PostgreSQL
- Persistence for orders, fills, trade logs  

### • Redis
- Realtime pub/sub and caching  

### • Nginx
- Optional reverse proxy  

### • Prometheus + Grafana
- Metrics and dashboards  

---

## 3. Hardware & OS Requirements
- MacBook Pro M2 Pro, 16GB  
- macOS Sequoia 15.6.1  
- Docker Desktop with Rosetta/QEMU emulation  
- Docker Compose v2+  

---

## 4. Directory Layout
```
local-ibkr-api/
  docker-compose.yml
  .env
  services/
    stocks-api/
      Dockerfile
      app/
        main.py
        ib_client.py
        routers/
    stocks-webapp/
      Dockerfile
      src/
  monitoring/
    prometheus.yml
  nginx/
    nginx.conf
```

---

## 5. Docker Compose – Local Integration

### Is `platform: linux/amd64` correct?
Yes — Required for Apple Silicon machines.

### Full service block with previously missing items restored:
```yaml
stocks-ib-gateway:
  image: ghcr.io/gnzsnz/ib-gateway:stable
  platform: linux/amd64
  container_name: stocks-ib-gateway
  environment:
    TWS_USERID: ${STOCKS_TWS_USERID}
    TWS_PASSWORD: ${STOCKS_TWS_PASSWORD}
    TRADING_MODE: paper
    AUTO_RESTART_TIME: "01:00"
    TIME_ZONE: "America/New_York"
  ports:
    - "127.0.0.1:5001:4003"
    - "127.0.0.1:5002:4004"
    - "127.0.0.1:5900:5900"
  volumes:
    - stocks-settings:/home/ibgateway/Jts
    - stocks-logs:/var/log/ibgateway
  healthcheck:
    test: ["CMD", "pgrep", "-f", "ibgateway"]
    interval: 30s
    timeout: 10s
    retries: 3
  restart: unless-stopped
```

Other volumes added:
```yaml
postgres:
  volumes:
    - stocks-db-data:/var/lib/postgresql/data

stocks-fastapi:
  volumes:
    - stocks-api-logs:/app/logs
```

React web app additions:
```yaml
stocks-webapp:
  container_name: stocks-webapp
  environment:
    REACT_APP_API_URL: http://localhost:8001
    REACT_APP_CONTAINER_TYPE: stocks
```

Bottom-level volumes (previously missing):
```yaml
volumes:
  stocks-settings:
  stocks-logs:
  stocks-api-logs:
  stocks-db-data:
```

---

## 6. Configuration & Secrets

### 6.1 `.env` File
```
STOCKS_TWS_USERID=your_ibkr_username
STOCKS_TWS_PASSWORD=your_ibkr_password_or_ibc_macro
STOCKS_TRADING_MODE=paper
STOCKS_JWT_SECRET=super_long_random_secret
ENVIRONMENT=development
```

### 6.2 IB Gateway / IBC Specifics
- Paper trading must be enabled  
- Time zone must be America/New_York  
- AUTO_RESTART_TIME should reflect IB policy  
- gnzsnz image automates 2FA and login  

---

## 8. Metrics Collection

### 8.1 Setup
- Grafana dashboards for performance, trading metrics, container health  
- Alerts for 2FA timeout, errors, failures  

### Prometheus Metrics
```python
from prometheus_client import Counter, Histogram, Gauge
```

### 8.2 Business Metrics
```python
orders_total = Counter('orders_total', 'Total orders',['container','order_type'])
order_latency = Histogram('order_latency_seconds','Order latency')
active_positions = Gauge('active_positions_total','Active positions',['container'])
pnl_unrealized = Gauge('pnl_unrealized_total','Unrealized P&L',['account'])
```

### 8.3 System Metrics
```python
api_requests_total = Counter('api_requests_total','API requests',['method','endpoint'])
api_request_duration = Histogram('api_request_duration_seconds','Duration')
ib_connection_status = Gauge('ib_connection_status','Gateway status',['container'])
```

### 8.4 Alerting Rules

#### Critical Alerts:
- Gateway disconnected  
- Database unreachable  
- High order rejection  
- Position breaches  
- Abnormal P&L movements  

#### Warning Alerts:
- High latency  
- Low disk space  
- Memory > 80%  
- Failed logins  
- Market data delays  

---

## 9. Development Best Practices

### 9.10 Code Organization
- Modular services  
- Dependency injection  
- Pydantic validation  
- OpenAPI documentation  
- Structured error handling  

### 9.12 Testing Strategy
- Unit tests  
- Integration tests  
- End-to-end trading tests  
- Load testing  
- Mock IB responses  

### 9.20 Operational Best Practices
- CPU/memory limits  
- Health checks  
- Graceful shutdown  
- Centralized logging  
- Backup schedules  

### 9.22 Security Best Practices
- No hardcoded secrets  
- Isolated networks  
- Least-privilege access  
- Regular updates  
- Audit logging  

### 9.3 Trading Best Practices
- Stop-loss automation  
- Circuit breakers  
- Pre-trade risk checks  
- Execution quality tracking  
- Partial fill handling  
- Robust cancellation  

### 9.4 Performance Best Practices
- IBKR connection pooling  
- Caching  
- Async operations  
- Respect IBKR rate limits  
- Batch operations  

---

## 10. Limitations
- IBKR pacing limits  
- Required daily restarts  
- One account per gateway instance  
- High memory use for gateway  
- FastAPI uses ~100 MB RAM  

---

END OF DOCUMENT
