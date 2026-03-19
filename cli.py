"""
CLI entry point for the Binance Futures Testnet trading bot.
"""

from __future__ import annotations

import argparse
import os
import sys

# Ensure local imports work when running directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env if available
try:
    from dotenv import load_dotenv
    load_dotenv()
    _DOTENV_AVAILABLE = True
except ImportError:
    _DOTENV_AVAILABLE = False

from client import BinanceFuturesClient, BinanceClientError, BinanceNetworkError
from logging_config import configure_logging, get_logger
from orders import place_order, print_order_summary
from validators import validate_order_params

__version__ = "1.0.0"

logger = get_logger(__name__)


# ---------------------------
# Argument Parser
# ---------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading-bot",
        description="Place orders on Binance Futures Testnet (USDT-M).",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    parser.add_argument("--symbol", required=True, help="e.g. BTCUSDT")
    parser.add_argument("--side", required=True, choices=["BUY", "SELL"])
    parser.add_argument("--type", dest="order_type", required=True,
                        choices=["MARKET", "LIMIT", "STOP_MARKET", "STOP"])
    parser.add_argument("--quantity", required=True, help="Order quantity")

    parser.add_argument("--price", required=False)
    parser.add_argument("--stop-price", dest="stop_price", required=False)

    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    parser.add_argument("--no-validate", action="store_true", help="Skip symbol validation")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logs")

    return parser


# ---------------------------
# Load Credentials
# ---------------------------
def load_credentials():
    api_key = os.getenv("BINANCE_TESTNET_API_KEY", "").strip()
    api_secret = os.getenv("BINANCE_TESTNET_API_SECRET", "").strip()

    if not api_key or not api_secret:
        print("\n[ERROR] Missing API credentials\n", file=sys.stderr)
        print("Create a .env file:\n", file=sys.stderr)
        print("BINANCE_TESTNET_API_KEY=your_key", file=sys.stderr)
        print("BINANCE_TESTNET_API_SECRET=your_secret\n", file=sys.stderr)
        sys.exit(1)

    return api_key, api_secret


# ---------------------------
# Confirmation
# ---------------------------
def confirm_order(params: dict) -> bool:
    try:
        answer = input("  ➤  Type 'yes' to confirm: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.", file=sys.stderr)
        return False

    return answer == "yes"


# ---------------------------
# MAIN
# ---------------------------
def run():
    parser = build_parser()
    args = parser.parse_args()

    configure_logging(verbose=args.verbose)

    logger.info("Bot started")

    api_key, api_secret = load_credentials()
    client = BinanceFuturesClient(api_key, api_secret)

    try:
        params = validate_order_params(
            symbol=args.symbol,
            side=args.side,
            order_type=args.order_type,
            quantity=args.quantity,
            price=args.price,
            stop_price=args.stop_price,
            client=None if args.no_validate else client,
        )
    except Exception as e:
        print(f"\n[ERROR] {e}\n", file=sys.stderr)
        sys.exit(1)

    # Quantity safety
    if float(params["quantity"]) <= 0:
        print("\n[INVALID INPUT] Quantity must be greater than zero\n", file=sys.stderr)
        sys.exit(1)

    # Show summary
    print_order_summary(params)

    # Confirm
    if not args.yes:
        if not confirm_order(params):
            print("\nOrder cancelled.\n")
            sys.exit(0)

    # Place order
    try:
        result = place_order(client, params)
    except BinanceClientError as e:
        print(f"\n[API ERROR] {e}\n", file=sys.stderr)
        sys.exit(1)
    except BinanceNetworkError as e:
        print(f"\n[NETWORK ERROR] {e}\n", file=sys.stderr)
        sys.exit(1)

    # Success output
    print("\n--- Order Response ---")
    print(result)
    print("\n✅ Order placed successfully!\n")

    logger.info("Bot finished successfully")


if __name__ == "__main__":
    run()