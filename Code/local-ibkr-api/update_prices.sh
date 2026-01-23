#!/bin/bash
# Updates conditional order prices by calling positions endpoint
while true; do
    # Calling positions updates market data in memory
    curl -s http://localhost:8000/positions/ > /dev/null
    
    # Now check conditions
    echo "$(date '+%H:%M:%S') - Checking conditions..."
    curl -s -X POST http://localhost:8000/conditional/check | jq -r '.message'
    
    sleep 10
done
