#!/bin/bash
echo "🚀 IBKR Local API - Test Suite"
echo "=============================="
echo ""

echo "Test 1: System Health Check"
curl -s http://localhost:8000/health | python3 -m json.tool
echo ""

echo "Test 2: API Root"
curl -s http://localhost:8000/ | python3 -m json.tool
echo ""

echo "Test 3: Place Market Order (TSLA)"
curl -s -X POST http://localhost:8000/orders/ \
  -H 'Content-Type: application/json' \
  -d '{"action":"BUY","currency":"USD","exchange":"SMART","order_type":"MKT","quantity":5,"sec_type":"STK","symbol":"TSLA","time_in_force":"DAY"}' \
  | python3 -m json.tool
echo ""

echo "Test 4: Place Limit Order (GOOGL)"
curl -s -X POST http://localhost:8000/orders/ \
  -H 'Content-Type: application/json' \
  -d '{"action":"BUY","currency":"USD","exchange":"SMART","limit_price":175.00,"order_type":"LMT","quantity":10,"sec_type":"STK","symbol":"GOOGL","time_in_force":"DAY"}' \
  | python3 -m json.tool
echo ""

echo "Test 5: List All Orders"
curl -s http://localhost:8000/orders/ | python3 -m json.tool
echo ""

echo "Test 6: View Positions"
curl -s http://localhost:8000/positions/ | python3 -m json.tool
echo ""

echo "Test 7: Account Summary"
curl -s http://localhost:8000/accounts/summary | python3 -m json.tool
echo ""

echo "Test 8: Get Order #1 Details"
curl -s http://localhost:8000/orders/1 | python3 -m json.tool
echo ""

echo "✅ All tests completed!"
