# Quick Setup for Team Members

## 🚀 60-Second Setup

1. **Clone & Configure:**
```bash
   git clone <repo-url>
   cd local-ibkr-api
   cp .env.example .env
```

2. **Edit `.env` - Add YOUR credentials:**
   - IB_USERNAME
   - IB_PASSWORD
   - IB_ACCOUNT

3. **Start Services:**
```bash
   docker compose up -d
```

4. **Configure Gateway (one-time):**
   - Get FastAPI IP: `docker inspect stocks-fastapi | grep IPAddress`
   - VNC to Gateway: `open vnc://127.0.0.1:5901` (password: ibgateway)
   - Add IP to: Configure → API → Settings → Trusted IPs
   - Restart: `docker compose restart stocks-ib-gateway`

5. **Verify (after 60 seconds):**
```bash
   curl http://localhost:8000/health
```

📖 **Full instructions:** See [SETUP.md](SETUP.md)
