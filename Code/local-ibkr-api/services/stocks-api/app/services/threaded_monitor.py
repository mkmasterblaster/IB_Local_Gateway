"""Thread-based conditional order monitor - avoids event loop conflicts."""
import threading
import time
import structlog
from datetime import datetime
from decimal import Decimal

from app.models.trading import ConditionalOrder, Order, OrderStatus, OrderType
from app.utils.database import SessionLocal

logger = structlog.get_logger()


class ThreadedConditionalMonitor:
    """Runs in separate thread with own event loop."""
    
    def __init__(self, check_interval=10):
        self.check_interval = check_interval
        self.running = False
        self.thread = None
        
    def start(self):
        """Start monitor in background thread."""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info("threaded_monitor_started", interval=self.check_interval)
        
    def stop(self):
        """Stop the monitor."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("threaded_monitor_stopped")
        
    def _run_loop(self):
        """Run in separate thread."""
        while self.running:
            try:
                self._check_conditions()
            except Exception as e:
                logger.error("monitor_check_error", error=str(e))
            
            time.sleep(self.check_interval)
            
    def _check_conditions(self):
        """Check all conditional orders."""
        db = SessionLocal()
        
        try:
            # Get active orders
            active_orders = db.query(ConditionalOrder).filter(
                ConditionalOrder.status == "ACTIVE"
            ).all()
            
            if not active_orders:
                return
                
            logger.info("monitor_checking", count=len(active_orders))
            
            for order in active_orders:
                try:
                    self._check_single_order(db, order)
                except Exception as e:
                    logger.error("monitor_order_error", order_id=order.id, error=str(e))
                    
        finally:
            db.close()
            
    def _check_single_order(self, db, order):
        """Check and execute single order."""
        # Use database price
        current_price = order.last_checked_price
        
        if not current_price:
            return
            
        # Check condition
        triggered = False
        if order.condition_type == "PRICE_ABOVE":
            triggered = current_price >= order.condition_price
        elif order.condition_type == "PRICE_BELOW":
            triggered = current_price <= order.condition_price
            
        if triggered:
            logger.info("monitor_triggered", order_id=order.id, symbol=order.condition_symbol, price=str(current_price))
            self._execute_order(db, order)
            
    def _execute_order(self, db, cond_order):
        """Execute the conditional order."""
        try:
            from app.utils.ib_dependencies import get_ib_client_singleton
            from ib_insync import Order as IBOrder, Stock
            
            ib_client = get_ib_client_singleton()
            
            contract = Stock(
                symbol=cond_order.order_symbol,
                exchange=cond_order.exchange,
                currency=cond_order.currency
            )
            
            ib_order = IBOrder()
            ib_order.orderId = ib_client.ib.client.getReqId()
            ib_order.action = cond_order.order_action
            ib_order.totalQuantity = cond_order.order_quantity
            ib_order.tif = cond_order.time_in_force
            
            if cond_order.order_type == "MKT":
                ib_order.orderType = "MKT"
            else:
                ib_order.orderType = "LMT"
                ib_order.lmtPrice = float(cond_order.order_limit_price)
            
            # Place order
            ib_client.ib.placeOrder(contract, ib_order)
            
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
            
            logger.info("monitor_executed", order_id=ib_order.orderId)
            
        except Exception as e:
            logger.error("execute_error", error=str(e))
            db.rollback()
