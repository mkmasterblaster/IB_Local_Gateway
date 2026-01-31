"""Check available IB algo strategies."""
from ib_insync import IB, Stock

ib = IB()
ib.connect('localhost', 4002, clientId=998)

# Get available algo params for different strategies
strategies = ['Vwap', 'Twap', 'Adaptive']

for strategy in strategies:
    print(f"\n{strategy} Parameters:")
    try:
        params = ib.whatIfOrder(
            Stock('AAPL', 'SMART', 'USD'),
            'BUY',
            100,
            orderType='LMT',
            lmtPrice=250,
            algoStrategy=strategy
        )
        print(f"  Supported: Yes")
    except Exception as e:
        print(f"  Error: {e}")

ib.disconnect()
