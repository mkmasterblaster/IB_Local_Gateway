# IBKR Local API

Local Interactive Brokers API integration for paper and live trading with FastAPI.

## Features

- 🔌 Real-time connection to IB Gateway
- 📊 Portfolio tracking and position monitoring
- 💼 Paper and live trading support
- 🐳 Fully containerized with Docker
- 📈 Integrated metrics and monitoring
- 🔒 Secure credential management

## Quick Start

**New team members:** See [SETUP.md](SETUP.md) for detailed setup instructions.

### Prerequisites
- Docker and Docker Compose
- Interactive Brokers account
- IB Gateway credentials

### Installation

1. **Clone and configure:**
```bash
   git clone <your-repo-url>
   cd local-ibkr-api
   cp .env.example .env
```

2. **Add your IB credentials to `.env`:**
   - IB_USERNAME
   - IB_PASSWORD
   - IB_ACCOUNT

3. **Start services:**
```bash
   docker compose up -d
```

4. **Configure Gateway Trusted IPs** (one-time setup - see [SETUP.md](SETUP.md))

5. **Verify connection:**
```bash
   curl http://localhost:8000/health
```

## Project Structure
```
.
├── services/
│   └── stocks-api/         # FastAPI application
├── docker-compose.yml      # Container orchestration
├── .env.example           # Environment template
└── SETUP.md              # Detailed setup guide
```

## Documentation

- [Team Setup Guide](SETUP.md) - Complete setup instructions
- [Quick Setup](README_TEAM_SETUP.md) - 60-second setup for team members

## Health Check
```bash
curl http://localhost:8000/health
```

Expected response:
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

## Security

⚠️ **Never commit `.env` files!** They contain sensitive credentials.

## Support

Contact the team lead for assistance.
