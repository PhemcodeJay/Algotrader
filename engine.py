import os
import time
import json
from datetime import datetime
from dotenv import load_dotenv
import logging
import signal_generator

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

import db  # this imports the db module
from signal_generator import get_usdt_symbols, analyze
from bybit_client import BybitClient
from ml import MLFilter

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

DEFAULT_SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", 900))  # 15 minutes
DEFAULT_TOP_N_SIGNALS = int(os.getenv("TOP_N_SIGNALS", 5))


class TradingEngine:
    def __init__(self):
        print("[Engine] 🚀 Initializing TradingEngine...")
        self.client = BybitClient()
        self.db = db.db
        self.ml = MLFilter()
        self.signal_generator = signal_generator

    def get_settings(self):
        scan_interval = self.db.get_setting("SCAN_INTERVAL")
        top_n_signals = self.db.get_setting("TOP_N_SIGNALS")
        scan_interval = int(scan_interval) if scan_interval else DEFAULT_SCAN_INTERVAL
        top_n_signals = int(top_n_signals) if top_n_signals else DEFAULT_TOP_N_SIGNALS
        return scan_interval, top_n_signals

    def update_settings(self, updates: dict):
        for key, value in updates.items():
            self.db.update_setting(key, value)

    def reset_to_defaults(self):
        self.db.reset_all_settings_to_defaults()

    def save_signal_pdf(self, signal: dict):
        filename = f"reports/signals/{signal.get('Symbol', 'UNKNOWN')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        c = canvas.Canvas(filename, pagesize=letter)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, 750, f"Signal Report for {signal.get('Symbol', 'UNKNOWN')}")
        c.setFont("Helvetica", 10)

        y = 730
        for key, val in signal.items():
            c.drawString(50, y, f"{key}: {val}")
            y -= 15
            if y < 50:
                c.showPage()
                y = 750
                c.setFont("Helvetica", 10)

        c.save()
        print(f"[Engine] ✅ Saved signal PDF: {filename}")

    def save_trade_pdf(self, trade: dict):
        filename = f"reports/trades/{trade.get('symbol', 'UNKNOWN')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        c = canvas.Canvas(filename, pagesize=letter)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, 750, f"Trade Report for {trade.get('symbol', 'UNKNOWN')}")
        c.setFont("Helvetica", 10)

        y = 730
        for key, val in trade.items():
            c.drawString(50, y, f"{key}: {val}")
            y -= 15
            if y < 50:
                c.showPage()
                y = 750
                c.setFont("Helvetica", 10)

        c.save()
        print(f"[Engine] ✅ Saved trade PDF: {filename}")

    def run_once(self):
        print("[Engine] 🔍 Scanning Binance Futures market...\n")
        scan_interval, top_n_signals = self.get_settings()
        signals = []
        symbols = get_usdt_symbols()

        for symbol in symbols:
            raw_signal = analyze(symbol)
            if raw_signal:
                enhanced = self.ml.enhance_signal(raw_signal)
                print(
                    f"✅ ML Signal: {enhanced.get('Symbol', 'UNKNOWN')} "
                    f"({enhanced.get('Side', 'N/A')} @ {enhanced.get('Entry', 'N/A')}) → "
                    f"Score: {enhanced.get('score', 0)}%"
                )

                self.db.add_signal({
                    "symbol": enhanced.get("Symbol", ""),
                    "interval": enhanced.get("Interval", "15m"),
                    "signal_type": enhanced.get("Side", ""),
                    "score": enhanced.get("score", 0.0),
                    "indicators": enhanced,
                })

                self.save_signal_pdf(enhanced)
                signals.append(enhanced)

            time.sleep(0.2)

        if not signals:
            print("[Engine] ⚠️ No tradable signals found.")
            return []

        signals.sort(key=lambda x: x.get('score', 0), reverse=True)
        top_signals = signals[:top_n_signals]

        for signal in top_signals:
            print(
                f"[Engine] 🧠 Executing trade for {signal.get('Symbol', 'UNKNOWN')} "
                f"(Score: {signal.get('score', 0)}%)"
            )

            is_real = getattr(self.client, "use_real", False)

            if is_real:
                print(f"[Engine] 🔁 Placing LIVE order on mainnet for {signal.get('Symbol')}")
            else:
                print(f"[Engine] 🧪 Simulating VIRTUAL trade on testnet for {signal.get('Symbol')}")

            try:
                order_response = self.client.place_order(
                    symbol=signal.get("Symbol", ""),
                    side=signal.get("Side", ""),
                    order_type=signal.get("OrderType", "Market"),
                    qty=signal.get("Qty", 0),
                    price=signal.get("Entry", 0.0),
                    time_in_force=signal.get("TIF", "GoodTillCancel"),
                )
            except Exception as e:
                print(f"[Engine] ❌ Order placement failed: {e}")
                continue

            trade_record = {
                "symbol": signal.get("Symbol", ""),
                "side": signal.get("Side", ""),
                "qty": signal.get("Qty", 0),
                "entry_price": signal.get("Entry", 0.0),
                "exit_price": None,
                "pnl": None,
                "timestamp": datetime.now(),
                "status": "open",
                "order_id": order_response.get("order_id", "") if order_response else "",
                "virtual": not is_real,
            }

            self.db.add_trade(trade_record)
            self.save_trade_pdf(trade_record)

        if not getattr(self.client, "use_real", False):
            print("[Engine] 🧪 Monitoring virtual orders...")
            if hasattr(self.client, "monitor_virtual_orders"):
                self.client.monitor_virtual_orders()
            else:
                print("[Engine] ⚠️ monitor_virtual_orders() not implemented in BybitClient.")

        return top_signals

    def run_loop(self):
        print("[Engine] ♻️ Entering scan loop...\n")
        while True:
            try:
                self.run_once()
            except Exception as e:
                print(f"[Engine] ❌ Error: {e}")
            scan_interval, _ = self.get_settings()
            print(f"[Engine] ⏱️ Sleeping for {scan_interval} seconds...\n")
            time.sleep(scan_interval)

    def get_recent_trades(self, limit=10):
        try:
            trades = self.db.get_recent_trades(limit=limit)
            formatted = []
            for t in trades:
                formatted.append({
                    "symbol": t.symbol,
                    "side": t.side,
                    "qty": t.qty,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "pnl": t.pnl,
                    "status": t.status,
                    "order_id": t.order_id,
                    "timestamp": t.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    "virtual": t.virtual
                })
            return formatted
        except Exception as e:
            print(f"[Engine] ⚠️ Failed to get recent trades: {e}")
            return []

    def load_capital(self) -> dict:
        if self.client and hasattr(self.client, "get_balance"):
            try:
                return self.client.get_balance()
            except Exception as e:
                logger.warning(f"[Engine] ⚠️ get_balance() failed: {e}")
        else:
            logger.info("[Engine] ⚠️ Virtual mode or client has no get_balance(). Using fallback.")
            try:
                with open("capital.json", "r") as f:
                    data = json.load(f)
                    capital = float(data.get("capital", 100.0))
                    currency = data.get("currency", "USD")
                    return {"capital": capital, "currency": currency}
            except Exception as e:
                logger.warning(f"[Engine] ⚠️ Could not load capital.json: {e}")

        return {"capital": 100.0, "currency": "USD"}

    def get_daily_pnl(self):
        if hasattr(self.db, "get_daily_pnl_pct"):
            return self.db.get_daily_pnl_pct()
        else:
            print("[Engine] ⚠️ get_daily_pnl_pct() not implemented in DatabaseManager.")
            return None

    def calculate_win_rate(self, trades):
        if not trades:
            return 0.0
        wins = sum(1 for trade in trades if trade['pnl'] > 0)
        return round((wins / len(trades)) * 100, 2)

    def generate_signals(self, confidence_threshold: float = 70.0) -> list:
        signals = []
        symbols = self.signal_generator.get_usdt_symbols()

        for sym in symbols:
            try:
                result = self.signal_generator.analyze(sym)
                if result and result.get("Score", 0) >= confidence_threshold:
                    signals.append(result)
            except Exception as e:
                logger.warning(f"[Engine] ⚠️ Error analyzing {sym}: {e}")

        signals.sort(key=lambda x: x.get("Score", 0), reverse=True)
        return signals

    @property
    def default_settings(self):
        scan_interval = self.db.get_setting("SCAN_INTERVAL")
        top_n_signals = self.db.get_setting("TOP_N_SIGNALS")
        max_loss_pct = self.db.get_setting("MAX_LOSS_PCT")
        return {
            "SCAN_INTERVAL": int(scan_interval) if scan_interval else DEFAULT_SCAN_INTERVAL,
            "TOP_N_SIGNALS": int(top_n_signals) if top_n_signals else DEFAULT_TOP_N_SIGNALS,
            "MAX_LOSS_PCT": float(max_loss_pct) if max_loss_pct else -5.0
        }


# Exportable engine instance
engine = TradingEngine()
