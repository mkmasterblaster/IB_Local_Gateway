"""Initialize database tables."""
import sys
sys.path.insert(0, '/app')

from app.utils.database import engine, Base
from app.models.trading import Order, Fill, Position, AccountSnapshot, TradingSession

print("Creating database tables...")

# Create all tables
Base.metadata.create_all(bind=engine)

print("✅ Database tables created successfully!")
print("Tables created:")
print("  - orders")
print("  - fills")
print("  - positions")
print("  - account_snapshots")
print("  - trading_sessions")
