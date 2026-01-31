"""
Conditional Order Monitor - checks conditions and executes orders.
Event-loop safe version for FastAPI.
"""
import asyncio
from datetime import datetime
from decimal import Decimal
import structlog

from sqlalchemy.orm import Session
from ib_insync import Stock

from app.models.trading import ConditionalOrder, Order, OrderStatus, OrderType
from app.utils.database import SessionLocal
from app.ib_client import IBKRClient
from app.config import MARKET_DATA_TYPE, CONDITIONAL_CHECK_PRICE_WAIT

logger = structlog.get_logger()


class ConditionalOrderMonitor:
    """Monitors and executes conditional orders in background."""
    
    def __init__(self, ib_client: IBKRClient):
        self.ib_client = ib_client
        self.running = False
        self.check_interval = 10  # Check every 10 seconds
        self.task = None
        
    async def start(self):
        """Start monitoring in background."""
        if self.running:
            logger.warning("conditional_monitor_already_running")
            return
            
        self.running = True
        logger.info("conditional_monitor_started", interval=self.check_interval)
        
        while self.running:
            try:
                await self._check_all_conditions()
            except Exception as e:
                logger.error("conditional_monitor_check_error", error=str(e))
            
            await asyncio.sleep(self.check_interval)
    
    def stop(self):
        """Stop monitoring."""
        self.running = False
        logger.info("conditional_monitor_stopped")
    
    async def _check_all_conditions(self):
        """Check all active conditional orders."""
        db = SessionLocal()
        
        try:
            # Set delayed market data
            self.ib_client.ib.reqMarketDataType(MARKET_DATA_TYPE)
            
            # Get all active orders
            active_orders = db.query(ConditionalOrder).filter(
                ConditionalOrder.status == "ACTIVE"
            ).all()
            
            if not active_orders:
                return
            
            logger.info("monitor_checking_orders", count=len(active_orders))
            
            for cond_order in active_orders:
                try:
                    await self._check_single_condition(db, cond_order)
                except Exception as e:
                    logger.error(
                        "monitor_check_single_error",
                        condition_id=cond_order.id,
                        error=str(e)
                    )
                    
        finally:
            db.close()
    
    async def _check_single_condition(self, db: Session, cond_order: ConditionalOrder):
        """Check a single conditional order."""
        # Get current price
        contract = Stock(
            symbol=cond_order.condition_symbol,
            exchange=cond_order.exchange,
            currency=cond_order.currency
        )
        
        # Qualify contract
        self.ib_client.ib.qualifyContracts(contract)
        
        # Request ticker
        tickers = self.ib_client.ib.reqTickers(contract)
        await asyncio.sleep(CONDITIONAL_CHECK_PRICE_WAIT)
        
        # Get price
        current_price = None
        if tickers and len(tickers) > 0:
            ticker = tickers[0]
            if ticker.last and ticker.last > 0:
                current_price = Decimal(str(ticker.last))
            elif ticker.close and ticker.close > 0:
                current_price = Decimal(str(ticker.close))
        
        if not current_price:
            return
        
        # Update last checked
        cond_order.last_checked_price = current_price
        cond_order.last_checked_at = datetime.utcnow()
        db.commit()
        
        # Check condition
        condition_met = False
        if cond_order.condition_type == "PRICE_ABOVE":
            condition_met = current_price >= cond_order.condition_price
        elif cond_order.condition_type == "PRICE_BELOW":
            condition_met = current_price <= cond_order.condition_price
        
        if condition_met:
            logger.info(
                "monitor_condition_triggered",
                condition_id=cond_order.id,
                symbol=cond_order.condition_symbol,
                current_price=str(current_price),
                trigger_price=str(cond_order.condition_price)
            )
            await self._execute_order(db, cond_order)
    
    async def _execute_order(self, db: Session, cond_order: ConditionalOrder):
        """Execute order when condition is met."""
        try:
            from ib_insync import Order as IBOrder
            
            contract = Stock(
                symbol=cond_order.order_symbol,
                exchange=cond_order.exchange,
                currency=cond_order.currency
            )
            
            ib_order = IBOrder()
            ib_order.orderId = self.ib_client.ib.client.getReqId()
            ib_order.action = cond_order.order_action
            ib_order.totalQuantity = cond_order.order_quantity
            ib_order.tif = cond_order.time_in_force
            
            if cond_order.order_type == "MKT":
                ib_order.orderType = "MKT"
            else:
                ib_order.orderType = "LMT"
                ib_order.lmtPrice = float(cond_order.order_limit_price)
            
            # Place order
            trade = self.ib_client.ib.placeOrder(contract, ib_order)
            
            # Store in database
            db_order = Order(
                order_id=ib_order.orderId,
                symbol=cond_order.order_symbol,
                action=cond_order.order_action,
                order_type=OrderType.MARKET if cond_order.order_type == "MKT" else OrderType.LIMIT,
                total_quantity=cond_order.order_quantity,
                limit_price=cond_order.order_limit_price if cond_order.order_type == "LMT" else None,
                status=OrderStatus.SUBMITTED,
                time_in_force=cond_order.time_in_force,
                client_id=999,
                sec_type="STK",
                exchange=cond_order.exchange,
                currency=cond_order.currency,
                filled_quantity=0,
                remaining_quantity=cond_order.order_quantity,
                risk_check_passed=True
            )
            db.add(db_order)
            
            # Update conditional order
            cond_order.status = "TRIGGERED"
            cond_order.triggered_at = datetime.utcnow()
            cond_order.executed_order_id = ib_order.orderId
            
            db.commit()
            
            logger.info(
                "monitor_order_executed",
                condition_id=cond_order.id,
                order_id=ib_order.orderId
            )
            
        except Exception as e:
            logger.error(
                "monitor_execute_error",
                condition_id=cond_order.id,
                error=str(e)
            )
            db.rollback()
