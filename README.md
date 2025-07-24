---

# 📈 AlgoTrader - Crypto Signal Scanner & Auto-Trading Engine

`ALGOTRADER` is a **real-time crypto signal and trading engine** that blends **multi-timeframe technical analysis**, **machine learning signal filtering**, and **Bybit USDT futures execution** into one automated loop.

It scans high-volume crypto pairs on Bybit, identifies strong entries using indicators like EMA, RSI, MACD, ATR, and Bollinger Bands, ranks signals by score and confidence, filters them using ML, then executes real or virtual trades. It logs everything to a PostgreSQL database and exports signal reports to PDF, Discord, and Reddit.

---

## 🚀 Features

* 📊 **Multi-Timeframe Technical Signal Scanner**
  Analyzes 15m, 1h, and 4h candles using:

  * EMA (9, 21), SMA (20)
  * RSI, MACD, ATR
  * Bollinger Bands
  * Trend detection and breakout regime classification

* 🧠 **ML-Based Signal Filtering**
  Each signal passes through `MLFilter` for scoring enhancement and filtering based on Z-score, confidence, and historical performance.

* 💹 **Hybrid Trading Engine**
  Trades can be executed in:

  * **REAL mode**: via Bybit API
  * **VIRTUAL mode**: simulated in memory

* 📦 **PostgreSQL + JSON Logging**
  Signals and trades are stored in:

  * PostgreSQL (via SQLAlchemy)
  * JSON files for redundancy and traceability

* 📤 **PDF Signal Reports + Social Posting**

  * Top 20 signals saved to `/reports/*.pdf`
  * Top 5 signals sent to **Discord** and **Reddit**

* 📈 **Smart Trade Structuring**
  Signals include:

  * Entry, TP, SL, trailing stop
  * Trend type: Scalp / Swing / Trend
  * Risk regime: Mean vs. Breakout

---

## 🧱 Project Structure

```
├── hybrid_engine.py       # Main engine (entry point)
├── database.py            # SQLAlchemy ORM manager
├── bybit_client.py        # Trading interface (real/virtual)
├── data_provider.py       # OHLCV + price feed from Bybit
├── exports.py             # PDF export + Discord/Reddit hooks
├── ml.py                  # Signal filtering + scoring enhancement
├── utils.py               # Helpers: pricing, JSON saving, etc.
├── reports/               # Exported signal PDFs
├── signals/               # Signal logs (JSON)
├── trades/                # Trade logs (JSON)
```

---

## ⚙️ Configuration

| Parameter               | Description                              | Default      |
| ----------------------- | ---------------------------------------- | ------------ |
| `REAL_MODE`             | Enables real Bybit trading               | `false`      |
| `ML_ENABLED`            | Enables ML signal enhancement            | `true`       |
| `TOP_SYMBOL_LIMIT`      | Top Bybit USDT symbols by volume to scan | `100`        |
| `TOP_TERMINAL_LIMIT`    | Signals shown in terminal                | `5`          |
| `TOP_PDF_LIMIT`         | Signals exported to PDF                  | `20`         |
| `SCAN_INTERVAL_MINUTES` | Time between each scan                   | `15`         |
| `UTC_OFFSET`            | Timezone offset for logging              | `+3` (UTC+3) |

Set environment variables in your `.env`:

```env
REAL_MODE=false
ML_ENABLED=true
```

---

## 📈 Signal Logic

A signal is considered valid only if:

* Trend direction is **consistent** across 15m, 1h, and 4h timeframes
* Signal passes the **ML filter**
* Final **Score ≥ 60** and **Confidence ≥ 70**

Each signal includes:

* `symbol`, `side` (LONG/SHORT)
* `entry`, `tp`, `sl`, `trail`
* `score`, `confidence`, `margin`, `liq_price`
* `trend`, `regime` (Mean/Breakout), `type` (Scalp/Swing/Trend)
* Timestamp (UTC+3)

---

## 🛒 Trade Execution

Trades are placed with the following logic:

* Position size = `(wallet_balance * 0.75) / entry_price`
* Orders include TP, SL, and trailing stop
* Order results are captured:

  * If `REAL_MODE=true`: executes on Bybit
  * If `REAL_MODE=false`: simulates execution
* All trades are saved to DB and `trades/*.json`

---

## 📤 Output & Alerts

After each scan:

* ✅ Top 5 signals are:

  * Printed to terminal
  * Posted to Discord & Reddit
* 📝 Top 20 signals are:

  * Exported to PDF (`/reports/signals_<timestamp>.pdf`)
* 🧠 All valid signals are:

  * Saved to JSON in `/signals/`
  * Logged in PostgreSQL via `db_manager`

---

## 🔁 Execution Loop

Run with:

```bash
python app.py
```

Every 15 minutes, the engine performs:

1. Get top Bybit symbols by volume
2. Fetch multi-timeframe OHLCV
3. Compute indicators
4. Generate and filter signals
5. Display/log/export/alert
6. Auto-place trades
7. Sleep for `SCAN_INTERVAL_MINUTES`

---

## ✅ Requirements

* Python 3.9+
* Bybit API keys via `.env`
* PostgreSQL database (configured in `database.py`)
* Install dependencies:

```bash
pip install ta numpy pandas sqlalchemy pybit praw reportlab python-dotenv
```

---

## 📌 Notes

* Works with both real and paper trading accounts
* Ideal for swing/short-term futures strategies
* Fully modular: you can extend each component individually
* Use `.env` to switch modes and enable/disable ML logic

---

## 🧠 Future Enhancements

* Backtest mode with historical OHLCV
* Telegram Bot alerts
* Portfolio rebalancing & optimization
* Configurable strategy presets (Scalp / Trend / Mean Reversion)
* Web dashboard with Streamlit integration

---

## 📫 Contact

**Developer**: OL'PHEMIE JEGEDE
**Project**: `AlgoTrader - Crypto Engine Suite`
**Platform**: Bybit USDT Futures

For support, collaboration, or API help — feel free to reach out!

---
