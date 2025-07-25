import os
import json
from datetime import datetime, date
from typing import List, Optional, Dict
from sqlalchemy import create_engine, String, Integer, Float, DateTime, Boolean, JSON, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session, Mapped, mapped_column
from sqlalchemy import func 

Base = declarative_base()

# === SQLAlchemy Models ===

class Signal(Base):
    __tablename__ = 'signals'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String)
    interval: Mapped[str] = mapped_column(String)
    signal_type: Mapped[str] = mapped_column(String)
    score: Mapped[float] = mapped_column(Float)
    indicators: Mapped[dict] = mapped_column(JSON)
    strategy: Mapped[str] = mapped_column(String, default="Default")  # ✅ New field
    side: Mapped[str] = mapped_column(String, default="LONG")         # ✅ New field
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Trade(Base):
    __tablename__ = 'trades'
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String)
    side: Mapped[str] = mapped_column(String)
    qty: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    status: Mapped[str] = mapped_column(String)
    order_id: Mapped[str] = mapped_column(String)
    virtual: Mapped[bool] = mapped_column(Boolean, default=True)


class Portfolio(Base):
    __tablename__ = 'portfolio'
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String, unique=True)
    qty: Mapped[float] = mapped_column(Float)
    avg_price: Mapped[float] = mapped_column(Float)
    value: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    capital: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)


class SystemSetting(Base):
    __tablename__ = 'settings'
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    value: Mapped[str] = mapped_column(String)


# === Database Manager ===

class DatabaseManager:
    def __init__(self, db_url: str):
        self.engine = create_engine(db_url, echo=False)
        self.Session = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)  # Run only once or on migration
        self.settings = {
            "SCAN_INTERVAL": 900,       # 15 minutes
            "TOP_N_SIGNALS": 5,
            "MAX_LOSS_PCT": -15.0,
            "TP_PERCENT": 0.30,         # 30%
            "SL_PERCENT": 0.15,         # 15%
            "LEVERAGE": 20,          # 20x leverage
            "RISK_PER_TRADE": 0.01,     # 1%
        }
        self._load_settings_from_file()

    def get_session(self) -> Session:
        return self.Session()

    def add_signal(self, signal_data: Dict):
        with self.get_session() as session:
            signal = Signal(**signal_data)
            session.add(signal)
            session.commit()

    def get_signals(self, symbol: Optional[str] = None, limit: int = 50) -> List[Signal]:
        with self.get_session() as session:
            query = session.query(Signal).order_by(Signal.created_at.desc())
            if symbol:
                query = query.filter(Signal.symbol == symbol)
            return query.limit(limit).all()
        
    def get_popular_symbols(self, limit: int = 10) -> List[str]:
        with self.get_session() as session:
            results = (
                session.query(Trade.symbol, func.count(Trade.symbol).label("symbol_count"))
                .group_by(Trade.symbol)
                .order_by(func.count(Trade.symbol).desc())
                .limit(limit)
                .all()
            )
            return [symbol for symbol, _ in results]

    def add_trade(self, trade_data: Dict):
        with self.get_session() as session:
            trade = Trade(**trade_data)
            session.add(trade)
            session.commit()

    def get_trades(self, symbol: Optional[str] = None, limit: int = 50) -> List[Trade]:
        with self.get_session() as session:
            query = session.query(Trade).order_by(Trade.timestamp.desc())
            if symbol:
                query = query.filter(Trade.symbol == symbol)
            return query.limit(limit).all()
        
    def get_recent_trades(self, limit: int = 10) -> List[Trade]:
        with self.get_session() as session:
            return session.query(Trade).order_by(Trade.timestamp.desc()).limit(limit).all()

    def update_portfolio_balance(self, symbol: str, qty: float, avg_price: float, value: float):
        with self.get_session() as session:
            portfolio = session.query(Portfolio).filter_by(symbol=symbol).first()
            if portfolio:
                portfolio.qty = qty
                portfolio.avg_price = avg_price
                portfolio.value = value
                portfolio.updated_at = datetime.now()
            else:
                portfolio = Portfolio(
                    symbol=symbol,
                    qty=qty,
                    avg_price=avg_price,
                    value=value,
                    updated_at=datetime.now()
                )
                session.add(portfolio)
            session.commit()

    def get_portfolio(self, symbol: Optional[str] = None) -> List[Portfolio]:
        with self.get_session() as session:
            if symbol:
                return session.query(Portfolio).filter_by(symbol=symbol).all()
            return session.query(Portfolio).all()

    def set_setting(self, key: str, value: str):
        with self.get_session() as session:
            setting = session.query(SystemSetting).filter_by(key=key).first()
            if setting:
                setting.value = value
            else:
                setting = SystemSetting(key=key, value=value)
                session.add(setting)
            session.commit()

    def get_setting(self, key: str) -> Optional[str]:
        with self.get_session() as session:
            setting = session.query(SystemSetting).filter_by(key=key).first()
            return setting.value if setting else None

    def get_all_settings(self) -> Dict[str, str]:
        with self.get_session() as session:
            settings = session.query(SystemSetting).all()
            return {s.key: s.value for s in settings}

    def get_open_trades(self) -> List[Trade]:
        with self.get_session() as session:
            return session.query(Trade).filter(Trade.status == 'open').all()

    def close_trade(self, order_id: str, exit_price: float, pnl: float):
        with self.get_session() as session:
            trade = session.query(Trade).filter_by(order_id=order_id).first()
            if trade:
                trade.exit_price = exit_price
                trade.pnl = pnl
                trade.status = 'closed'
                session.commit()

    def get_automation_stats(self) -> Dict[str, str]:
        return {
            "total_signals": str(len(self.get_signals())),
            "open_trades": str(len(self.get_open_trades())),
            "timestamp": str(datetime.now())
        }

    def get_daily_pnl_pct(self) -> float:
        with self.get_session() as session:
            today = date.today()
            trades = session.query(Trade).filter(
                Trade.status == 'closed',
                Trade.timestamp >= datetime(today.year, today.month, today.day)
            ).all()

            total_pnl = sum(t.pnl for t in trades if t.pnl is not None)
            total_entry = sum(t.entry_price * t.qty for t in trades if t.entry_price is not None and t.qty is not None)

            if total_entry == 0:
                return 0.0

            return round((total_pnl / total_entry) * 100, 2)

    def update_automation_stats(self, stats: dict):
        with self.get_session() as session:
            setting = session.query(SystemSetting).filter_by(key="AUTOMATION_STATS").first()
            if setting:
                setting.value = json.dumps(stats)
            else:
                setting = SystemSetting(key="AUTOMATION_STATS", value=json.dumps(stats))
                session.add(setting)
            session.commit()

    def _settings_file(self):
        return "settings.json"

    def _load_settings_from_file(self):
        if os.path.exists(self._settings_file()):
            try:
                with open(self._settings_file(), "r") as f:
                    file_settings = json.load(f)
                    self.settings.update(file_settings)
                    print("[DB] ✅ Loaded settings from settings.json")
            except Exception as e:
                print(f"[DB] ⚠️ Failed to load settings: {e}")
        else:
            self._save_settings_to_file()

    def _save_settings_to_file(self):
        try:
            with open(self._settings_file(), "w") as f:
                json.dump(self.settings, f, indent=4)
                print("[DB] 💾 Settings saved to file")
        except Exception as e:
            print(f"[DB] ❌ Failed to save settings: {e}")

    def update_setting(self, key, value):
        self.settings[key] = value
        self._save_settings_to_file()
        print(f"[DB] ⚙️ Updated setting {key} → {value}")

    def reset_all_settings_to_defaults(self):
        self.settings = {
            "SCAN_INTERVAL": 900,
            "TOP_N_SIGNALS": 5,
            "MAX_LOSS_PCT": -15.0,
            "TP_PERCENT": 0.30,
            "SL_PERCENT": 0.15,
            "LEVERAGE": 20,
            "RISK_PER_TRADE": 0.01,
        }
        self._save_settings_to_file()
        print("[DB] 🔄 Settings reset to default values")

    # ---- New helper methods for views/db page ----

    def get_db_health(self) -> dict:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_signals_count(self) -> int:
        with self.get_session() as session:
            return session.query(Signal).count()

    def get_trades_count(self) -> int:
        with self.get_session() as session:
            return session.query(Trade).count()

    def get_portfolio_count(self) -> int:
        with self.get_session() as session:
            return session.query(Portfolio).count()


# === Global instance ===

db_url = os.getenv("DATABASE_URL", "sqlite:///trading.db")
db_manager = DatabaseManager(db_url=db_url)

# Optional alias for convenience
db = db_manager
