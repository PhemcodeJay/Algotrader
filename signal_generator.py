import requests
from datetime import datetime, timedelta, timezone
from time import sleep
import pytz
from db import SessionLocal, Signal  # Make sure these are defined in db.py

# === CONFIGURATION ===
RISK_PCT = 0.15
ACCOUNT_BALANCE = 100
LEVERAGE = 20
ENTRY_BUFFER_PCT = 0.002
MIN_VOLUME = 1000
MIN_ATR_PCT = 0.001
RSI_ZONE = (20, 80)
INTERVALS = ['15m', '1h', '4h']
MAX_SYMBOLS = 100
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/..."
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"

tz_utc3 = timezone(timedelta(hours=3))

# === NOTIFICATIONS ===
def send_discord(message):
    if DISCORD_WEBHOOK_URL:
        try:
            requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
        except Exception as e:
            print(f"Discord error: {e}")

def send_telegram(message):
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            requests.post(url, data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown"
            })
        except:
            pass

# === BYBIT DATA ===
def get_candles(sym, interval):
    interval_map = {"15m": "15", "1h": "60", "4h": "240"}
    url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={sym}&interval={interval_map[interval]}&limit=200"
    try:
        res = requests.get(url)
        data = res.json().get('result', {}).get('list', [])
        return [{
            'high': float(c[3]),
            'low': float(c[4]),
            'close': float(c[5]),
            'volume': float(c[6])
        } for c in data]
    except Exception as e:
        print(f"Failed to fetch {sym} candles: {e}")
        return []

# === INDICATORS ===
def ema(prices, period):
    if len(prices) < period:
        return None
    mult = 2 / (period + 1)
    val = sum(prices[:period]) / period
    for p in prices[period:]:
        val = (p - val) * mult + val
    return val

def sma(prices, period):
    return sum(prices[-period:]) / period if len(prices) >= period else None

def rsi(prices, period=14):
    if len(prices) < period + 1:
        return None
    gains = [max(prices[i] - prices[i-1], 0) for i in range(1, period + 1)]
    losses = [max(prices[i-1] - prices[i], 0) for i in range(1, period + 1)]
    ag, al = sum(gains) / period, sum(losses) / period
    rs = ag / (al + 1e-10)
    return 100 - (100 / (1 + rs))

def bollinger(prices, period=20, sd=2):
    mid = sma(prices, period)
    if mid is None:
        return None, None, None
    var = sum((p - mid) ** 2 for p in prices[-period:]) / period
    std = var ** 0.5
    return mid + sd * std, mid, mid - sd * std

def atr(highs, lows, closes, period=14):
    if len(highs) < period + 1:
        return None
    trs = [max(h - l, abs(h - c), abs(l - c)) for h, l, c in zip(highs[1:], lows[1:], closes[:-1])]
    val = sum(trs[:period]) / period
    for t in trs[period:]:
        val = (val * (period - 1) + t) / period
    return val

def macd(prices):
    fast = ema(prices, 12)
    slow = ema(prices, 26)
    return fast - slow if fast and slow else None

def classify_trend(ema9, ema21, sma20):
    if ema9 > ema21 > sma20:
        return "Trend"
    elif ema9 > ema21:
        return "Swing"
    return "Scalp"

# === ANALYSIS ===
def analyze(symbol):
    data = {}
    for tf in INTERVALS:
        candles = get_candles(symbol, tf)
        if len(candles) < 30:
            return None
        closes = [c['close'] for c in candles]
        volumes = [c['volume'] for c in candles]
        highs = [c['high'] for c in candles]
        lows = [c['low'] for c in candles]

        data[tf] = {
            'close': closes[-1],
            'ema9': ema(closes, 9),
            'ema21': ema(closes, 21),
            'sma20': sma(closes, 20),
            'rsi': rsi(closes),
            'macd': macd(closes),
            'bb_up': bollinger(closes)[0],
            'bb_mid': bollinger(closes)[1],
            'bb_low': bollinger(closes)[2],
            'atr': atr(highs, lows, closes),
            'volume': volumes[-1]
        }

    tf = data['1h']
    if tf['volume'] < MIN_VOLUME or tf['atr'] / tf['close'] < MIN_ATR_PCT or not (RSI_ZONE[0] < tf['rsi'] < RSI_ZONE[1]):
        return None

    sides = []
    for d in data.values():
        if d['close'] > d['bb_up']:
            sides.append('LONG')
        elif d['close'] < d['bb_low']:
            sides.append('SHORT')
        elif d['close'] > d['ema21']:
            sides.append('LONG')
        elif d['close'] < d['ema21']:
            sides.append('SHORT')

    if len(set(sides)) != 1:
        return None

    side = sides[0]
    price = tf['close']
    trend = classify_trend(tf['ema9'], tf['ema21'], tf['sma20'])
    bb_dir = "Up" if price > tf['bb_up'] else "Down" if price < tf['bb_low'] else "No"

    entry = min((v for v in [tf['sma20'], tf['ema9'], tf['ema21']] if v), key=lambda x: abs(x - price))
    tp = round(entry * (1.015 if side == 'LONG' else 0.985), 6)
    sl = round(entry * (0.985 if side == 'LONG' else 1.015), 6)
    trail = round(entry * (1 - ENTRY_BUFFER_PCT) if side == 'LONG' else entry * (1 + ENTRY_BUFFER_PCT), 6)
    liq = round(entry * (1 - 1 / LEVERAGE) if side == 'LONG' else entry * (1 + 1 / LEVERAGE), 6)
    margin = round((ACCOUNT_BALANCE * RISK_PCT) / LEVERAGE, 6)

    score = 0
    score += 0.3 if tf['macd'] > 0 else 0
    score += 0.2 if tf['rsi'] < 30 or tf['rsi'] > 70 else 0
    score += 0.3 if bb_dir != "No" else 0.1
    score += 0.2 if trend == "Trend" else 0.1

    return {
        'symbol': symbol,
        'side': side,
        'type': trend,
        'score': round(score * 100, 1),
        'entry': round(entry, 6),
        'tp': tp,
        'sl': sl,
        'trail': trail,
        'margin': margin,
        'market': price,
        'liq': liq,
        'bb_slope': bb_dir,
        'time': datetime.now(tz_utc3)
    }

# === FETCH SYMBOLS ===
def get_usdt_symbols():
    try:
        url = "https://api.bybit.com/v5/market/tickers?category=linear"
        res = requests.get(url)
        tickers = res.json().get('result', {}).get('list', [])
        return [t['symbol'] for t in sorted(tickers, key=lambda x: float(x['turnover24h']), reverse=True) if t['symbol'].endswith("USDT")][:MAX_SYMBOLS]
    except Exception as e:
        print(f"Symbol fetch failed: {e}")
        return []

# === SAVE SIGNAL TO DB ===
def save_signal_to_db(sig_data):
    session = SessionLocal()
    try:
        signal = Signal(**sig_data)
        session.add(signal)
        session.commit()
        print(f"✅ Saved: {sig_data['symbol']}")
    except Exception as e:
        session.rollback()
        print(f"❌ DB Save error: {e}")
    finally:
        session.close()

# === MAIN LOOP ===
def main():
    while True:
        print("\n🔍 Scanning Bybit USDT Perpetuals...\n")
        syms = get_usdt_symbols()
        signals = []

        for sym in syms:
            sig = analyze(sym)
            if sig:
                signals.append(sig)
                save_signal_to_db(sig)
            sleep(0.3)

        if signals:
            signals.sort(key=lambda x: x['score'], reverse=True)
            top5 = signals[:5]
            top_msg = "\n\n".join([f"""
==================== {s['symbol']} ====================
📊 TYPE: {s['type']}     📈 SIDE: {s['side']}     🏆 SCORE: {s['score']}%
💵 ENTRY: {s['entry']}   🎯 TP: {s['tp']}         🛡️ SL: {s['sl']}
💱 MARKET: {s['market']} 📍 BB: {s['bb_slope']}    🔄 Trail: {s['trail']}
⚖️ MARGIN: {s['margin']} ⚠️ LIQ: {s['liq']}
⏰ TIME: {s['time'].strftime('%Y-%m-%d %H:%M UTC+3')}
=========================================================""" for s in top5])

            send_discord(f"📊 **Top Signals**\n\n{top_msg}")
            send_telegram(f"📊 *Top Signals*\n\n{top_msg}")
            print("📤 Signals sent to Discord & Telegram.")
        else:
            print("⚠️ No valid signals.")

        print("♻️ Rescanning in 60 minutes...\n")
        sleep(3600)

if __name__ == "__main__":
    main()
