# Team Setup Guide

## Prerequisites
- Docker and Docker Compose installed
- Interactive Brokers account (paper trading account recommended for testing)
- IB Gateway credentials

## Quick Start

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd local-ibkr-api
```

### 2. Configure Your Credentials

**Copy the environment template:**
```bash
cp .env.example .env
```

**Edit `.env` with your IB credentials:**
```bash
# On Mac/Linux
nano .env

# Or use any text editor
open .env
```

**Required settings to change:**
- `IB_USERNAME` - Your IB username
- `IB_PASSWORD` - Your IB password  
- `IB_ACCOUNT` - Your IB account number (e.g., DU6992571 for paper trading)
- `IB_TRADING_MODE` - Set to `paper` for paper trading or `live` for live trading
- `POSTGRES_PASSWORD` - Choose a secure password
- `API_SECRET_KEY` - Generate with: `openssl rand -hex 32`

### 3. Configure IB Gateway Trusted IPs

**Important:** You must add your Docker network IP to IB Gateway's trusted IPs.

**a) Start the containers:**
```bash
docker compose up -d
```

**b) Get your FastAPI container's IP:**
```bash
docker inspect stocks-fastapi | grep IPAddress
# Look for the IP like 172.20.0.5
```

**c) Connect to IB Gateway via VNC:**
```bash
open vnc://127.0.0.1:5901
# Password: ibgateway
```

**d) Add the IP to Trusted IPs:**
1. In Gateway: **Configure → API → Settings**
2. Scroll to **"Trusted IPs"**
3. Click **"Create"**
4. Add the IP you found (e.g., `172.20.0.5`)
5. Your list should have:
   - `localhost`
   - `127.0.0.1`
   - `172.20.0.5` (or whatever IP you found)
6. Click **"OK"**
7. Restart Gateway: `docker compose restart stocks-ib-gateway`

### 4. Verify Connection

**Wait 60 seconds for Gateway to fully start, then:**
```bash
curl http://localhost:8000/health
```

**You should see:**
```json
{
  "status": "healthy",
  "services": {
    "api": "running",
    "database": "healthy",
    "redis": "healthy",
    "ib_gateway": "connected"
  }
}
```

## Troubleshooting

### Connection fails with "TimeoutError"
- Check that you added your container's IP to Trusted IPs in Gateway
- Verify Gateway is running: `docker ps | grep ib-gateway`
- Check Gateway logs: `docker logs stocks-ib-gateway`

### "Invalid credentials" error
- Verify your IB_USERNAME and IB_PASSWORD in `.env`
- Make sure you're using the correct trading mode (paper vs live)
- Check if 2FA is enabled on your account (may need to disable for API access)

### Health check shows "ib_gateway": "disconnected"
- Restart FastAPI: `docker compose restart stocks-fastapi`
- Check FastAPI logs: `docker compose logs stocks-fastapi --tail=50`

## Security Notes

⚠️ **NEVER commit your `.env` file to git!**
- It contains your IB credentials and passwords
- `.env` is in `.gitignore` to prevent accidental commits
- Each team member maintains their own local `.env`

## Getting Help

If you encounter issues:
1. Check the logs: `docker compose logs`
2. Verify all containers are running: `docker ps`
3. Contact the team lead
