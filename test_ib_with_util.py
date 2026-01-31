from ib_insync import IB, util
import time

print("Starting util event loop...")
util.startLoop()

ib = IB()
print("Connecting to localhost:5001...")

ib.connect('127.0.0.1', 5001, clientId=777, timeout=30)

if ib.isConnected():
    print(f"✅ Connected! Accounts: {ib.managedAccounts()}")
    time.sleep(5)
    if ib.isConnected():
        print("✅ Still connected after 5 seconds!")
    ib.disconnect()
else:
    print("❌ Failed to connect")

util.stopLoop()
