"""Position management endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import structlog

from app.schemas.trading import PositionResponse
from app.models.trading import Position
from app.utils.database import get_db
from app.utils.ib_dependencies import get_ib_client
from app.ib_protocol import IBKRClientProtocol
from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/positions", tags=["positions"])


@router.get("/", response_model=List[PositionResponse])
async def list_positions(
    db: Session = Depends(get_db),
    ib_client: IBKRClientProtocol = Depends(get_ib_client)
):
    """
    Get current positions from IBKR.
    
    - Fetches live positions from IB Gateway
    - Updates database snapshot
    - Returns current positions with P&L
    """
    try:
        # Get positions from IBKR
        positions = await ib_client.get_positions(account=settings.STOCKS_ACCOUNT)
        
        # Store snapshot in database
        snapshot_time = datetime.utcnow()
        
        for pos in positions:
            db_position = Position(
                account=pos.account,
                symbol=pos.contract.symbol,
                sec_type=pos.contract.secType,
                exchange=pos.contract.exchange or "SMART",
                currency=pos.contract.currency or "USD",
                position_size=pos.position,
                avg_cost=pos.avgCost,
                market_price=0.0,  # Will be updated with market data
                market_value=0.0,
                unrealized_pnl=0.0,
                realized_pnl=0.0,
                snapshot_time=snapshot_time
            )
            db.add(db_position)
        
        db.commit()
        
        # Get portfolio items for P&L
        portfolio = await ib_client.get_portfolio_items(account=settings.STOCKS_ACCOUNT)
        
        result = []
        for item in portfolio:
            result.append(PositionResponse(
                id=0,
                account=item.account,
                symbol=item.contract.symbol,
                sec_type=item.contract.secType,
                position_size=item.position,
                avg_cost=item.averageCost,
                market_price=item.marketPrice,
                market_value=item.marketValue,
                unrealized_pnl=item.unrealizedPNL,
                realized_pnl=item.realizedPNL,
                snapshot_time=snapshot_time
            ))
        
        logger.info("positions_fetched", count=len(result))
        return result
        
    except Exception as e:
        logger.error("positions_fetch_failed", error=str(e))
        raise HTTPException(500, f"Failed to fetch positions: {str(e)}")


@router.get("/{symbol}", response_model=PositionResponse)
async def get_position(
    symbol: str,
    db: Session = Depends(get_db),
    ib_client: IBKRClientProtocol = Depends(get_ib_client)
):
    """Get position details for a specific symbol."""
    try:
        positions = await ib_client.get_positions(account=settings.STOCKS_ACCOUNT)
        
        for pos in positions:
            if pos.contract.symbol == symbol.upper():
                portfolio = await ib_client.get_portfolio_items(account=settings.STOCKS_ACCOUNT)
                
                for item in portfolio:
                    if item.contract.symbol == symbol.upper():
                        return PositionResponse(
                            id=0,
                            account=item.account,
                            symbol=item.contract.symbol,
                            sec_type=item.contract.secType,
                            position_size=item.position,
                            avg_cost=item.averageCost,
                            market_price=item.marketPrice,
                            market_value=item.marketValue,
                            unrealized_pnl=item.unrealizedPNL,
                            realized_pnl=item.realizedPNL,
                            snapshot_time=datetime.utcnow()
                        )
        
        raise HTTPException(404, f"No position found for {symbol}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("position_fetch_failed", symbol=symbol, error=str(e))
        raise HTTPException(500, f"Failed to fetch position: {str(e)}")
