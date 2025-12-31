from ib_insync import IB
import asyncio

async def test():
    ib = IB()
    print("Connecting to localhost:5001 (Gateway port 4002 mapped)...")
    
    try:
        await ib.connectAsync('127.0.0.1', 5001, clientId=888, timeout=30)
        print(f"✅ Connected! isConnected={ib.isConnected()}")
        
        print("Waiting 5 seconds to see if connection stays alive...")
        await asyncio.sleep(5)
        
        if ib.isConnected():
            print("✅ Still connected after 5 seconds!")
            print(f"Accounts: {ib.managedAccounts()}")
        else:
            print("❌ Disconnected during wait")
            
        ib.disconnect()
    except Exception as e:
        print(f"❌ Connection error: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test())
