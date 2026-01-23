# Switching to Real-Time Market Data

## Current Setup
The system uses **delayed market data** (15-20 minute delay) which requires no subscription.

## To Enable Real-Time Data

1. **Subscribe to IB Market Data**
   - Log into your IB account
   - Subscribe to market data for the exchanges you need
   - Common: US Securities Snapshot and Futures Value Bundle

2. **Update Configuration**
   Edit `services/stocks-api/app/config.py`:
```python
   MARKET_DATA_TYPE = 1  # Change from 3 to 1
```

3. **Restart the API**
```bash
   docker compose restart stocks-fastapi
```

## Market Data Types
- `1` = Real-time (requires subscription) ← **Use this when subscribed**
- `2` = Frozen (for testing)
- `3` = Delayed (15-20 min delay, no subscription) ← **Current setting**
- `4` = Delayed-Frozen

## Testing
After enabling real-time data, test with:
```bash
curl -X POST http://localhost:8000/conditional/check | jq
```

The prices should now be real-time instead of delayed.
