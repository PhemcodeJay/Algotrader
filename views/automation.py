import os
import streamlit as st
import time
from datetime import datetime

def render(trading_engine, dashboard, automated_trader):
    st.title("🤖 AlgoTrader Automation")
    status = automated_trader.get_status()
    stats = status["stats"]

    col1, col2, col3 = st.columns(3)
    col1.metric("Automation Status", "🟢 Active" if status.get("is_running") else "🔴 Off")
    col2.metric("Signals Generated", stats["signals_generated"])
    col3.metric("Trades Executed", stats["trades_executed"])

    col1, col2, col3 = st.columns(3)
    with col1:
        if not status["is_running"]:
            if st.button("▶️ Start Auto Mode"):
                if automated_trader.start_automation():
                    st.success("Automation started")
                    time.sleep(1); st.rerun()
                else:
                    st.error("Failed to start")
        else:
            if st.button("⏹️ Stop Automation"):
                if automated_trader.stop_automation():
                    st.success("Automation stopped")
                    time.sleep(1); st.rerun()
                else:
                    st.error("Stop failed")

    with col2:
        if st.button("🔄 Generate Signals"):
            with st.spinner("Generating…"):
                signals = automated_trader.generate_automated_signals()
                st.success(f"Generated {len(signals)} signals")
    with col3:
        if st.button("📊 View Logs"):
            log_file = "automated_trader.log"
            if os.path.exists(log_file):
                logs = open(log_file).read().splitlines()[-20:]
                st.text_area("Recent Logs", "\n".join(logs), height=200)
            else:
                st.info("No log file found")

    st.markdown("---")
    st.subheader("⚙️ Automation Settings")
    col1, col2 = st.columns(2)
    with col1:
        signal_interval = st.slider("Signal Interval (min)", 5, 60, status["settings"]["signal_interval"]//60)
        min_conf = st.slider("Min Confidence %", 50, 95, status["settings"]["min_confidence"])
        max_signals = st.slider("Max Signals/cycle", 1, 10, status["settings"]["max_signals_per_cycle"])
    with col2:
        exec_trades = st.checkbox("Enable Trade Execution", value=status["settings"]["trade_execution"])
        max_daily = st.slider("Max Daily Trades", 1, 150, status["settings"]["max_daily_trades"])
        max_pos = st.slider("Max Position Size %", 0.5, 20.0, float(status["settings"]["max_position_size_pct"]), step=0.5)
        max_dd = st.slider("Max Drawdown %", 0.0, 100.0, 10.0, step=0.1)

    if st.button("💾 Save Automation Settings"):
        new = {
            "signal_interval": signal_interval*60,
            "trade_execution": exec_trades,
            "min_confidence": min_conf,
            "max_signals": max_signals,
            "max_daily_trades": max_daily,
            "max_position_size": max_pos,
            "max_drawdown": max_dd
        }
        if automated_trader.update_settings(new):
            st.success("Settings saved")
            time.sleep(1); st.rerun()
        else:
            st.error("Save failed")

    st.subheader("📈 Automation Performance")
    col1, col2, col3, col4 = st.columns(4)
    success_rate = stats["successful_trades"] / stats["trades_executed"] * 100 if stats["trades_executed"] else 0
    col1.metric("Total Signals", stats["signals_generated"])
    col2.metric("Total Trades", stats["trades_executed"])
    col3.metric("Success Rate", f"{success_rate:.1f}%")
    col4.metric("Total P&L", f"${dashboard.format_currency(stats['total_pnl'])}")

    if status["is_running"]:
        st.subheader("⏰ Timing Information")
        last = datetime.fromisoformat(status["last_signal_generation"])
        nxt = datetime.fromisoformat(status["next_signal_generation"])
        st.info(f"Last Signal Generation: {last:%Y-%m-%d %H:%M:%S}")
        st.info(f"Next Signal Generation: {nxt:%Y-%m-%d %H:%M:%S}")
