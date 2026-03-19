# Binance Futures Testnet Trading Bot

A Python CLI-based trading bot that places orders on Binance Futures Testnet (USDT-M).
Designed with clean architecture, input validation, logging, and robust error handling.

---

## 🚀 Features

* Place MARKET and LIMIT orders
* Supports BUY and SELL sides
* CLI interface using argparse
* Input validation (symbol, quantity, order type)
* Structured logging of API requests and responses
* Retry handling for network/API issues
* Confirmation prompt before order execution

---

## 🧱 Project Structure

```
cli.py               # CLI entry point
client.py            # Binance API client
orders.py            # Order placement logic
validators.py        # Input validation
logging_config.py    # Logging setup
```

---

## ⚙️ Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```
BINANCE_TESTNET_API_KEY=your_key
BINANCE_TESTNET_API_SECRET=your_secret
```

---

## ▶️ Usage

### MARKET Order

```bash
python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
```

### LIMIT Order

```bash
python cli.py --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 60000
```

---

## 📄 Example Output

```
Order Summary:
Symbol: BTCUSDT
Side: BUY
Type: MARKET
Quantity: 0.001

Type 'yes' to confirm:

--- Order Response ---
Order ID: 123456
Status: FILLED
Executed Qty: 0.001
Avg Price: 65000

Order placed successfully!
```

---

## 🧠 Note

The bot successfully connects to Binance Futures Testnet and validates trading symbols.
Order requests are correctly constructed and sent. In some cases, execution may be restricted due to API permission limitations on the testnet environment.

---

## 📌 Tech Stack

* Python 3.x
* requests / httpx
* argparse
* python-dotenv
* logging

---

## 📬 Author

Parameswar Swain
