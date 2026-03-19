"""
Binance Futures Testnet API client wrapper.
Handles authentication, HMAC signing, retries, and raw HTTP communication.
"""

import hashlib
import hmac
import time
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from logging_config import get_logger

logger = get_logger(__name__)

# Binance Futures Testnet base URL
TESTNET_BASE_URL = "https://testnet.binancefuture.com"

# Retry configuration
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 0.5          # waits: 0 s, 0.5 s, 1.0 s between retries
RETRY_STATUS_CODES = {500, 502, 503, 504}


class BinanceClientError(Exception):
    """Raised when the Binance API returns an application-level error response."""

    def __init__(self, status_code: int, error_code: int, message: str) -> None:
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        super().__init__(f"[HTTP {status_code}] Binance error {error_code}: {message}")


class BinanceNetworkError(Exception):
    """Raised when a network-level failure occurs (timeout, DNS, connection refused)."""


class BinanceFuturesClient:
    """
    Thin wrapper around the Binance Futures Testnet REST API.

    Responsibilities:
      - Persistent session with automatic connection pooling
      - HMAC-SHA256 request signing
      - Transparent retry logic for transient failures
      - Structured error propagation
    """

    def __init__(self, api_key: str, api_secret: str) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = TESTNET_BASE_URL
        self.session = self._build_session()

    # ------------------------------------------------------------------
    # Session & transport
    # ------------------------------------------------------------------

    def _build_session(self) -> requests.Session:
        """
        Create a persistent session with:
          - Default auth headers
          - Automatic retry on idempotent requests + server errors
        """
        session = requests.Session()
        session.headers.update(
            {
                "X-MBX-APIKEY": self.api_key,
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )

        retry_strategy = Retry(
            total=MAX_RETRIES,
            backoff_factor=RETRY_BACKOFF_FACTOR,
            status_forcelist=RETRY_STATUS_CODES,
            allowed_methods={"GET", "POST", "DELETE"},
            raise_on_status=False,  # We handle status ourselves
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        return session

    # ------------------------------------------------------------------
    # Signing
    # ------------------------------------------------------------------

    def _sign(self, params: dict) -> dict:
        """Append a server timestamp and HMAC-SHA256 signature to *params* (mutates in place)."""
        params["timestamp"] = int(time.time() * 1000)
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    # ------------------------------------------------------------------
    # Core request dispatcher with manual retry + back-off
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        sign: bool = True,
    ) -> dict:
        """
        Execute an HTTP request against the Binance API with retry support.

        The session-level Retry handles transport-layer retries (5xx, resets).
        This manual loop adds application-level retries with logging so every
        attempt is visible in the log file.

        Args:
            method:   HTTP verb (GET, POST, DELETE).
            endpoint: API path, e.g. ``/fapi/v1/order``.
            params:   Query / body parameters (will be signed if *sign* is True).
            sign:     Whether to attach an HMAC-SHA256 signature.

        Returns:
            Parsed JSON response dict.

        Raises:
            BinanceClientError:  API rejected the request (4xx / meaningful 5xx).
            BinanceNetworkError: Could not reach the endpoint after all retries.
        """
        params = params or {}
        if sign:
            params = self._sign(params)

        url = f"{self.base_url}{endpoint}"
        safe_params = {k: v for k, v in params.items() if k not in {"signature", "timestamp"}}
        logger.debug("→ %s %s | params: %s", method, url, safe_params)

        last_exc: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self.session.request(method, url, params=params, timeout=10)
                break  # Successful HTTP round-trip; proceed to parse response

            except requests.exceptions.ConnectionError as exc:
                last_exc = exc
                logger.warning(
                    "Attempt %d/%d — connection error: %s",
                    attempt, MAX_RETRIES, exc,
                )
            except requests.exceptions.Timeout as exc:
                last_exc = exc
                logger.warning(
                    "Attempt %d/%d — request timed out after 10 s",
                    attempt, MAX_RETRIES,
                )

            if attempt < MAX_RETRIES:
                sleep_s = RETRY_BACKOFF_FACTOR * (2 ** (attempt - 1))
                logger.info("Retrying in %.1f s …", sleep_s)
                time.sleep(sleep_s)
        else:
            # Exhausted all retries without a successful connection
            raise BinanceNetworkError(
                f"Failed to reach {url} after {MAX_RETRIES} attempts: {last_exc}"
            ) from last_exc

        logger.debug("← HTTP %s | body: %.500s", response.status_code, response.text)

        # Binance always returns JSON, even for errors
        try:
            data = response.json()
        except ValueError:
            raise BinanceClientError(
                response.status_code, -1, "Non-JSON response received"
            )

        if not response.ok:
            raise BinanceClientError(
                status_code=response.status_code,
                error_code=data.get("code", -1),
                message=data.get("msg", "Unknown error"),
            )

        return data

    # ------------------------------------------------------------------
    # Public API helpers
    # ------------------------------------------------------------------

    def get_exchange_info(self) -> dict:
        """Fetch exchange metadata (symbols, filters, precision, trading rules)."""
        return self._request("GET", "/fapi/v1/exchangeInfo", sign=False)

    def place_order(self, **kwargs) -> dict:
        """
        Submit a new futures order.

        Keyword arguments map 1-to-1 with Binance ``/fapi/v1/order`` parameters:
        symbol, side, type, quantity, price, timeInForce, stopPrice, etc.
        """
        return self._request("POST", "/fapi/v1/order", params=kwargs)
