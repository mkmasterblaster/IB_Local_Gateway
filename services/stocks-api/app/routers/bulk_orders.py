"""Bulk Order Submission Endpoint."""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
import pandas as pd
import io
from ib_insync import Stock, MarketOrder, LimitOrder, StopOrder

from app.utils.database import get_db
from app.schemas.bulk_orders import BulkOrderInput, BulkOrderResponse
from app.utils.ib_dependencies import get_ib_client
from app.ib_client import IBKRClient
from app.models.trading import Order, OrderStatus as DBOrderStatus
import structlog

router = APIRouter(prefix="/bulk", tags=["bulk_orders"])
logger = structlog.get_logger(__name__)

@router.post("/upload", response_model=BulkOrderResponse)
async def upload_bulk_orders(
    file: UploadFile = File(...),
    validate_only: bool = False,
    ib_client: IBKRClient = Depends(get_ib_client),
    db: Session = Depends(get_db)
):
    """Upload and execute bulk orders from CSV/Excel."""
    try:
        contents = await file.read()
        
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(contents))
        elif file.filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(io.BytesIO(contents))
        else:
            raise HTTPException(400, "File must be CSV or Excel")
        
        logger.info("bulk_upload_received", rows=len(df), filename=file.filename)
        
        results = []
        successful = 0
        failed = 0
        
        for idx, row in df.iterrows():
            try:
                order_data = {k: v for k, v in row.to_dict().items() 
                             if pd.notna(v) and v != ''}
                
                order = BulkOrderInput(**order_data)
                
                if validate_only:
                    results.append({
                        "row": idx + 2,
                        "symbol": order.symbol,
                        "status": "validated",
                        "order_type": order.order_type
                    })
                    successful += 1
                else:
                    order_id = await _execute_order(order, ib_client, db)
                    results.append({
                        "row": idx + 2,
                        "symbol": order.symbol,
                        "status": "placed",
                        "order_id": order_id,
                        "order_type": order.order_type
                    })
                    successful += 1
                    
            except Exception as e:
                logger.error("bulk_order_failed", row=idx+2, error=str(e))
                results.append({
                    "row": idx + 2,
                    "symbol": row.get('symbol', 'UNKNOWN'),
                    "status": "failed",
                    "error": str(e)
                })
                failed += 1
        
        return BulkOrderResponse(
            total_orders=len(df),
            successful=successful,
            failed=failed,
            results=results
        )
        
    except Exception as e:
        logger.error("bulk_upload_error", error=str(e))
        raise HTTPException(500, f"Bulk upload failed: {str(e)}")


async def _execute_order(order: BulkOrderInput, ib_client: IBKRClient, db: Session) -> int:
    """Execute single order."""
    contract = Stock(symbol=order.symbol, exchange=order.exchange, currency=order.currency)
    
    if order.order_type == "MKT":
        ib_order = MarketOrder(order.action, order.quantity)
    elif order.order_type == "LMT":
        ib_order = LimitOrder(order.action, order.quantity, float(order.limit_price))
    elif order.order_type == "STP":
        ib_order = StopOrder(order.action, order.quantity, float(order.stop_price))
    else:
        raise ValueError(f"Order type {order.order_type} not yet implemented")
    
    ib_order.tif = order.time_in_force
    trade = await ib_client.place_order(contract, ib_order)
    return trade.order.orderId
