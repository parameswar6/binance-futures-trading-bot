"""
Input validation for order parameters.

All validators raise ``ValueError`` with a clear, actionable message on failure.
Symbol existence is verified against the live Binance exchange-info endpoint.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from logging_config import get_logger

if TYPE_CHECKING:
    from client import BinanceFuturesClient

logger = get_logger(__name__)

SUPPORTED_SIDES = {"BUY", "SELL"}
SUPPORTED_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET", "STOP"}


# ---------------------------------------------------------------------------
# Field-level validators
# ---------------------------------------------------------------------------


def validate_symbol(symbol: str) -> str:
    """Normalise and syntactically validate a trading symbol."""
    symbol = symbol.strip().upper()
    if not symbol:
        raise ValueError("Symbol must not be empty.")
    if not symbol.isalnum():
        raise ValueError(
            f"Symbol '{symbol}' contains invalid characters. "
            "Use alphanumeric only (e.g. BTCUSDT)."
        )
    return symbol


def validate_side(side: str) -> str:
    """Ensure *side* is BUY or SELL."""
    side = side.strip().upper()
    if side not in SUPPORTED_SIDES:
        raise ValueError(
            f"Side must be one of {sorted(SUPPORTED_SIDES)}, got '{side}'."
        )
    return side


def validate_order_type(order_type: str) -> str:
    """Ensure *order_type* is a supported Binance Futures order type."""
    order_type = order_type.strip().upper()
    if order_type not in SUPPORTED_ORDER_TYPES:
        raise ValueError(
            f"Order type must be one of {sorted(SUPPORTED_ORDER_TYPES)}, "
            f"got '{order_type}'."
        )
    return order_type


def validate_quantity(quantity: str) -> str:
    """Ensure *quantity* is a positive decimal number."""
    try:
        qty = Decimal(str(quantity))
    except InvalidOperation:
        raise ValueError(f"Quantity '{quantity}' is not a valid number.")
    if qty <= 0:
        raise ValueError(f"Quantity must be greater than zero, got {qty}.")
    return str(qty)


def validate_price(price: str, label: str = "Price") -> str:
    """Ensure a price-type field is a positive decimal number."""
    try:
        p = Decimal(str(price))
    except InvalidOperation:
        raise ValueError(f"{label} '{price}' is not a valid number.")
    if p <= 0:
        raise ValueError(f"{label} must be greater than zero, got {p}.")
    return str(p)


# ---------------------------------------------------------------------------
# Live symbol validation against Binance exchange info
# ---------------------------------------------------------------------------


def validate_symbol_on_exchange(symbol: str, client: "BinanceFuturesClient") -> None:
    """
    Confirm that *symbol* passes all three exchange-level checks:

    1. **Exists** on Binance Futures Testnet.
    2. **Status** is ``'TRADING'`` (not ``'BREAK'``, ``'END_OF_DAY'``, etc.).
    3. **Contract type** is ``'PERPETUAL'`` — i.e. a USDT-M perpetual future,
       not a quarterly delivery contract (``'CURRENT_QUARTER'`` etc.).

    Args:
        symbol: Already-normalised symbol string, e.g. ``'BTCUSDT'``.
        client: Authenticated client used to call ``/fapi/v1/exchangeInfo``.

    Raises:
        ValueError: Descriptive message for each distinct failure mode.
    """
    logger.debug("Fetching exchange info to validate symbol '%s' …", symbol)
    try:
        info = client.get_exchange_info()
    except Exception as exc:  # noqa: BLE001 — network errors re-raised as ValueError for UX
        raise ValueError(
            f"Could not fetch exchange info to validate symbol '{symbol}': {exc}"
        ) from exc

    # Index all symbols by name for O(1) lookup
    symbol_map: dict[str, dict] = {
        s["symbol"]: s for s in info.get("symbols", [])
    }

    # ── Check 1: symbol must exist at all ───────────────────────────────────
    if symbol not in symbol_map:
        # Surface a few valid examples from the live exchange for guidance
        examples = sorted(
            s for s in symbol_map if s.endswith("USDT")
        )[:5]
        example_str = ", ".join(examples) if examples else "BTCUSDT, ETHUSDT"
        raise ValueError(
            f"Symbol '{symbol}' was not found on Binance Futures Testnet.\n"
            f"  Available USDT examples: {example_str}\n"
            "  Double-check the symbol name and try again."
        )

    meta = symbol_map[symbol]

    # ── Check 2: symbol must be actively trading ─────────────────────────────
    status = meta.get("status", "UNKNOWN")
    if status != "TRADING":
        raise ValueError(
            f"Symbol '{symbol}' is currently not tradable (status='{status}').\n"
            "  It may be in a break, settlement, or pre-delivery period.\n"
            "  Check https://testnet.binancefuture.com for active markets."
        )

    # ── Check 3: must be a USDT-M perpetual (not a delivery contract) ────────
    contract_type = meta.get("contractType", "UNKNOWN")
    if contract_type != "PERPETUAL":
        raise ValueError(
            f"Symbol '{symbol}' is a '{contract_type}' contract, not a USDT-M perpetual.\n"
            "  This bot only supports perpetual futures (e.g. BTCUSDT, ETHUSDT).\n"
            "  Delivery / quarterly contracts are not supported."
        )

    logger.debug(
        "Symbol '%s' validated — status=%s, contractType=%s.",
        symbol, status, contract_type,
    )


# ---------------------------------------------------------------------------
# Composite validator (all fields + optional live check)
# ---------------------------------------------------------------------------


def validate_order_params(
    symbol: str,
    side: str,
    order_type: str,
    quantity: str,
    price: str | None = None,
    stop_price: str | None = None,
    client: "BinanceFuturesClient | None" = None,
) -> dict:
    """
    Run all validations and return a clean, API-ready parameter dict.

    Args:
        symbol:     Trading pair, e.g. ``'BTCUSDT'``.
        side:       ``'BUY'`` or ``'SELL'``.
        order_type: ``'MARKET'``, ``'LIMIT'``, ``'STOP_MARKET'``, or ``'STOP'``.
        quantity:   Order size as a string or number.
        price:      Required for ``LIMIT`` and ``STOP`` (limit) orders.
        stop_price: Required for ``STOP_MARKET`` and ``STOP`` orders.
        client:     If provided, symbol is verified against the live exchange.

    Returns:
        Dict of validated, normalised parameters ready to pass to the API.

    Raises:
        ValueError: Descriptive message for any validation failure.
    """
    params: dict = {
        "symbol":   validate_symbol(symbol),
        "side":     validate_side(side),
        "type":     validate_order_type(order_type),
        "quantity": validate_quantity(quantity),
    }

    order_type_norm = params["type"]

    # --- Price / TIF rules per order type ---
    if order_type_norm == "LIMIT":
        if price is None:
            raise ValueError("--price is required for LIMIT orders.")
        if stop_price is not None:
            raise ValueError("--stop-price must not be specified for LIMIT orders.")
        params["price"] = validate_price(price, label="Limit price")
        params["timeInForce"] = "GTC"

    elif order_type_norm == "MARKET":
        if price is not None:
            raise ValueError("--price must not be specified for MARKET orders.")
        if stop_price is not None:
            raise ValueError("--stop-price must not be specified for MARKET orders.")

    elif order_type_norm == "STOP_MARKET":
        if price is not None:
            raise ValueError(
                "--price must not be specified for STOP_MARKET orders. "
                "Use --stop-price to set the trigger price."
            )
        if stop_price is None:
            raise ValueError("--stop-price is required for STOP_MARKET orders.")
        params["stopPrice"] = validate_price(stop_price, label="Stop price")

    elif order_type_norm == "STOP":
        # STOP is a stop-limit order: needs both stopPrice and price
        if stop_price is None:
            raise ValueError(
                "--stop-price (trigger) is required for STOP (stop-limit) orders."
            )
        if price is None:
            raise ValueError(
                "--price (limit price) is required for STOP (stop-limit) orders."
            )
        params["stopPrice"] = validate_price(stop_price, label="Stop price")
        params["price"] = validate_price(price, label="Limit price")
        params["timeInForce"] = "GTC"

    # --- Live symbol check (requires a network call) ---
    if client is not None:
        validate_symbol_on_exchange(params["symbol"], client)

    return params
