import os
import json
import numpy as np
import pandas as pd
import joblib
from glob import glob
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split

# === Configuration Paths ===
MODEL_PATH = "ml_models/profit_xgb_model.pkl"
TRADE_PATH = "trades/trades.json"
SIGNAL_PATH = "signals/"

class MLFilter:
    def __init__(self):
        self.model = self._load_model()

    def _load_model(self):
        if os.path.exists(MODEL_PATH):
            print("[ML] ✅ Loaded trained model.")
            return joblib.load(MODEL_PATH)
        else:
            print("[ML] ⚠️ No trained model found. Using fallback scoring.")
            return None

    def extract_features(self, signal: dict) -> np.ndarray:
        """Convert signal dict to feature array for ML model input."""
        return np.array([
            signal.get("entry", 0),
            signal.get("tp", 0),
            signal.get("sl", 0),
            signal.get("trail", 0),
            signal.get("score", 0),
            signal.get("confidence", 0),
            1 if signal.get("side") == "LONG" else 0,
            1 if signal.get("trend") == "Up" else -1 if signal.get("trend") == "Down" else 0,
            1 if signal.get("regime") == "Breakout" else 0,
        ])

    def enhance_signal(self, signal: dict) -> dict:
        """Add score/confidence to signal using model (if available)."""
        if self.model:
            features = self.extract_features(signal).reshape(1, -1)
            prob = self.model.predict_proba(features)[0][1]
            signal["score"] = round(prob * 100, 2)
            signal["confidence"] = int(min(signal["score"] + np.random.uniform(0, 10), 100))
        else:
            # Fallback: use default values if model isn't trained
            signal["score"] = signal.get("score", 60)
            signal["confidence"] = signal.get("confidence", 70)
        return signal

    def append_live_trade(self, trade: dict):
        """Save a real trade to the training set."""
        os.makedirs(os.path.dirname(TRADE_PATH), exist_ok=True)
        if not os.path.exists(TRADE_PATH):
            with open(TRADE_PATH, "w") as f:
                json.dump([], f)

        with open(TRADE_PATH, "r+", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if not isinstance(data, list):
                    data = []
            except Exception:
                data = []

            data.append(trade)
            f.seek(0)
            json.dump(data, f, indent=2)
            f.truncate()

        print(f"[ML] ✅ New trade appended for training.")

    def load_signals_as_virtual_trades(self) -> list:
        """Turn saved signals into pseudo-trades with assumed profit."""
        virtual_trades = []
        signal_files = glob(os.path.join(SIGNAL_PATH, "*.json"))

        for path in signal_files:
            try:
                with open(path, "r") as f:
                    signal = json.load(f)

                trade = {
                    "symbol": signal.get("symbol"),
                    "entry": signal.get("entry"),
                    "tp": signal.get("tp"),
                    "sl": signal.get("sl"),
                    "trail": signal.get("trail", 0),
                    "score": signal.get("score"),
                    "confidence": signal.get("confidence"),
                    "side": signal.get("side"),
                    "trend": signal.get("trend"),
                    "regime": signal.get("regime", "Breakout"),
                    "profit": 1 if signal.get("score", 0) > 70 else 0
                }

                if all(k in trade and trade[k] is not None for k in ["entry", "tp", "sl", "score", "confidence", "side", "trend"]):
                    virtual_trades.append(trade)

            except Exception as e:
                print(f"[ML] ⚠️ Failed to load signal {path}: {e}")

        print(f"[ML] ✅ Loaded {len(virtual_trades)} virtual trades from signals.")
        return virtual_trades

    def train_from_history(self):
        """Train an XGBoost model on combined real + virtual trades."""
        all_trades = []

        # Load real trades
        if os.path.exists(TRADE_PATH):
            try:
                with open(TRADE_PATH, "r") as f:
                    real_trades = json.load(f)
                    if isinstance(real_trades, list):
                        all_trades.extend(real_trades)
                        print(f"[ML] ✅ Loaded {len(real_trades)} real trades.")
            except Exception as e:
                print(f"[ML] ⚠️ Failed to load trades.json: {e}")

        # Load synthetic trades from signals
        all_trades.extend(self.load_signals_as_virtual_trades())

        # Convert to DataFrame
        df = pd.DataFrame(all_trades)
        if df.empty or len(df) < 30:
            print(f"[ML] ❌ Not enough samples to train. Require ≥ 30, got {len(df)}.")
            return

        # Encode categorical columns
        df["side_enc"] = df["side"].map({"LONG": 1, "SHORT": 0})
        df["trend_enc"] = df["trend"].map({"Up": 1, "Down": -1, "Neutral": 0})
        df["regime_enc"] = df["regime"].map({"Breakout": 1, "Mean": 0})

        required_cols = ["entry", "tp", "sl", "trail", "score", "confidence", "side_enc", "trend_enc", "regime_enc"]
        if not all(col in df.columns for col in required_cols):
            print(f"[ML] ❌ Missing required columns. Check your data structure.")
            return

        X = df[required_cols]
        y = df["profit"]

        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Train model
        model = XGBClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            use_label_encoder=False,
            eval_metric="logloss"
        )
        model.fit(X_train, y_train)

        # Save model
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        joblib.dump(model, MODEL_PATH)
        self.model = model

        acc = model.score(X_test, y_test)
        print(f"[ML] ✅ Trained model from {len(df)} records. Accuracy: {acc:.2%}")


# === Standalone Training ===
if __name__ == "__main__":
    ml = MLFilter()
    ml.train_from_history()
