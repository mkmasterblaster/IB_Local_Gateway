from typing import Any, Dict
from fastapi import APIRouter
from app.utils.ib_dependencies import peek_ib_client_singleton

router = APIRouter(tags=["debug"])

@router.get("/debug/ib")
async def debug_ib() -> Dict[str, Any]:
    """Debug endpoint to inspect IB client state."""
    c = peek_ib_client_singleton()
    
    if c is None:
        return {"initialized": False}
    
    connected = bool(
        c.is_connected()
        if hasattr(c, "is_connected")
        else getattr(c, "connected", False)
    )
    
    ib = getattr(c, "ib", None)
    ib_sock = None
    if ib is not None:
        try:
            ib_sock = bool(ib.isConnected())
        except Exception:
            ib_sock = None
    
    return {
        "initialized": True,
        "connected": connected,
        "ib_socket_connected": ib_sock,
        "host": getattr(c, "host", None),
        "port": getattr(c, "port", None),
        "client_id": getattr(c, "client_id", None),
        "telemetry": {
            "connect_attempts": getattr(c, "connect_attempts", None),
            "reconnect_attempts": getattr(c, "reconnect_attempts", None),
            "last_connect_error": getattr(c, "last_connect_error", None),
            "last_connect_error_at": getattr(c, "last_connect_error_at", None),
            "last_connected_at": getattr(c, "last_connected_at", None),
            "last_disconnected_at": getattr(c, "last_disconnected_at", None),
        },
    }
