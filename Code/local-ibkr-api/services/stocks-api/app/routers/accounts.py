"""Account management endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import structlog

from app.schemas.trading import AccountSummaryResponse
from app.models.trading import AccountSnapshot
from app.utils.database import get_db
from app.utils.ib_dependencies import get_ib_client
from app.ib_protocol import IBKRClientProtocol
from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("/summary", response_model=AccountSummaryResponse)
async def get_account_summary(
    db: Session = Depends(get_db),
    ib_client: IBKRClientProtocol = Depends(get_ib_client)
):
    """
    Get account summary from IBKR.
    
    - Net liquidation value
    - Cash balances
    - Buying power
    - P&L (unrealized, realized, daily)
    - Margin information
    """
    try:
        # Get account summary from IBKR
        summary = await ib_client.get_account_summary(account=settings.STOCKS_ACCOUNT)
        
        snapshot_time = datetime.utcnow()
        
        # Store snapshot in database
        db_snapshot = AccountSnapshot(
            account=settings.STOCKS_ACCOUNT,
            net_liquidation=summary.get("NetLiquidation", 0.0),
            total_cash_value=summary.get("TotalCashValue", 0.0),
            settled_cash=summary.get("SettledCash", 0.0),
            buying_power=summary.get("BuyingPower", 0.0),
            gross_position_value=summary.get("GrossPositionValue", 0.0),
            unrealized_pnl=summary.get("UnrealizedPnL", 0.0),
            realized_pnl=summary.get("RealizedPnL", 0.0),
            daily_pnl=summary.get("DailyPnL", 0.0),
            available_funds=summary.get("AvailableFunds", 0.0),
            excess_liquidity=summary.get("ExcessLiquidity", 0.0),
            cushion=summary.get("Cushion", 0.0),
            snapshot_time=snapshot_time
        )
        
        db.add(db_snapshot)
        db.commit()
        
        logger.info("account_summary_fetched", account=settings.STOCKS_ACCOUNT)
        
        return AccountSummaryResponse(
            account=settings.STOCKS_ACCOUNT,
            net_liquidation=summary.get("NetLiquidation", 0.0),
            total_cash_value=summary.get("TotalCashValue", 0.0),
            buying_power=summary.get("BuyingPower", 0.0),
            gross_position_value=summary.get("GrossPositionValue", 0.0),
            unrealized_pnl=summary.get("UnrealizedPnL", 0.0),
            realized_pnl=summary.get("RealizedPnL", 0.0),
            daily_pnl=summary.get("DailyPnL", 0.0),
            available_funds=summary.get("AvailableFunds", 0.0),
            excess_liquidity=summary.get("ExcessLiquidity", 0.0),
            cushion=summary.get("Cushion", 0.0),
            snapshot_time=snapshot_time
        )
        
    except Exception as e:
        logger.error("account_summary_failed", error=str(e))
        raise HTTPException(500, f"Failed to fetch account summary: {str(e)}")
