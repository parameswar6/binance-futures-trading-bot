"""
Order placement logic and response formatting.

Decouples business logic from the CLI and HTTP client layers.
Supports MARKET, LIMIT, STOP_MARKET, and STOP (stop-limit) order types.
"""

from __future__ import annotations

from client import BinanceFuturesClient, BinanceClientError, BinanceNetworkError  # noqa: F401 (re-exported)
from logging_config import get_logger

logger = get_logger(__name__)

# Order types that carry a limit price in the response
_PRICE_BEARING_TYPES = {"LIMIT", "STOP"}


class OrderResult:
    """
    Wraps a raw Binance order response and provides a formatted __str__.

    All fields default to ``'N/A'`` when absent so callers never need to
    defensively check individual keys.
    """

    def __init__(self, raw: dict) -> None:
        self.raw = raw
        self.order_id: int | str = raw.get("orderId", "N/A")
        self.client_order_id: str = raw.get("clientOrderId", "N/A")
        self.symbol: str = raw.get("symbol", "N/A")
        self.status: str = raw.get("status", "N/A")
        self.side: str = raw.get("side", "N/A")
        self.order_type: str = raw.get("type", "N/A")
        self.orig_qty: str = raw.get("origQty", "N/A")
        self.executed_qty: str = raw.get("executedQty", "N/A")
        self.avg_price: str = raw.get("avgPrice") or raw.get("price") or "N/A"
        self.stop_price: str = raw.get("stopPrice", "N/A")
        self.time_in_force: str = raw.get("timeInForce", "N/A")
        self.update_time: int | str = raw.get("updateTime", "N/A")

    def __str__(self) -> str:
        divider = "─" * 52

        # Status badge — makes FILLED vs NEW immediately clear
        status_badge = {
            "FILLED":            "✅ FILLED",
            "NEW":               "🕐 NEW (resting)",
            "PARTIALLY_FILLED":  "⏳ PARTIALLY FILLED",
            "CANCELED":          "❌ CANCELED",
            "EXPIRED":           "⚠️  EXPIRED",
        }.get(self.status, self.status)

        lines = [
            "",
            divider,
            "  📦 ORDER CONFIRMED",
            divider,
            f"  {'Order ID':<14}: {self.order_id}",
            f"  {'Symbol':<14}: {self.symbol}",
            f"  {'Status':<14}: {status_badge}",
            f"  {'Side':<14}: {self.side}",
            f"  {'Type':<14}: {self.order_type}",
            f"  {'Orig Qty':<14}: {self.orig_qty}",
            f"  {'Executed Qty':<14}: {self.executed_qty}",
            f"  {'Avg Price':<14}: {self.avg_price} USDT",
        ]

        if self.stop_price not in ("N/A", "0", "0.00000000"):
            lines.append(f"  {'Stop Price':<14}: {self.stop_price} USDT")

        if self.time_in_force != "N/A":
            lines.append(f"  {'Time-in-Force':<14}: {self.time_in_force}")

        lines.append(divider)
        lines.append("")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pre-order summary
# ---------------------------------------------------------------------------


def print_order_summary(params: dict) -> None:
    """
    Print a clearly formatted order preview *before* the user is asked to
    confirm. Includes a visual BUY/SELL badge so the direction is obvious
    at a glance.
    """
    divider = "─" * 52
    side    = params["side"]
    # Visual direction badge — makes misclicks obvious before they cost money
    badge   = "🟢 BUY " if side == "BUY" else "🔴 SELL"

    lines = [
        "",
        divider,
        f"  📋 ORDER PREVIEW                  {badge}",
        divider,
        f"  {'Symbol':<14}: {params['symbol']}",
        f"  {'Side':<14}: {params['side']}",
        f"  {'Order Type':<14}: {params['type']}",
        f"  {'Quantity':<14}: {params['quantity']}",
    ]

    if "price" in params:
        lines.append(f"  {'Limit Price':<14}: {params['price']} USDT")
    if "stopPrice" in params:
        lines.append(f"  {'Stop Price':<14}: {params['stopPrice']} USDT")
    if "timeInForce" in params:
        lines.append(f"  {'Time-in-Force':<14}: {params['timeInForce']}")

    lines.append(divider)
    lines.append("")
    print("\n".join(lines))


# ---------------------------------------------------------------------------
# Order placement
# ---------------------------------------------------------------------------


def place_order(client: BinanceFuturesClient, params: dict) -> OrderResult:
    """
    Submit a validated order to Binance and return a structured result.

    Args:
        client: An authenticated :class:`BinanceFuturesClient` instance.
        params: A validated parameter dict produced by
                :func:`validators.validate_order_params`.

    Returns:
        :class:`OrderResult` wrapping the API response.

    Raises:
        BinanceClientError:  API rejected the order (bad params, insufficient
                             balance, precision violation, etc.).
        BinanceNetworkError: Could not reach the API after all retries.
    """
    logger.info(
        "Submitting %s %s order | symbol=%s qty=%s price=%s stop=%s",
        params["side"],
        params["type"],
        params["symbol"],
        params["quantity"],
        params.get("price", "—"),
        params.get("stopPrice", "—"),
    )

    raw_response = client.place_order(**params)

    logger.info(
        "Order accepted | orderId=%s status=%s",
        raw_response.get("orderId"),
        raw_response.get("status"),
    )
    logger.debug("Full API response: %s", raw_response)

    return OrderResult(raw_response)
