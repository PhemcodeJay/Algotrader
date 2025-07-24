import streamlit as st
from datetime import datetime, timezone

def render(trading_engine, dashboard):
    st.title("💼 Wallet Summary")

    # Fetch balance info safely
    balance_info = trading_engine.load_capital()
    capital = balance_info.get("capital", 0.0)
    currency = balance_info.get("currency", "USD")
    start_balance = 100.0  # You can optionally load this from settings if needed

    trades = trading_engine.get_recent_trades()

    # Compute total return
    total_return_pct = ((capital - start_balance) / start_balance) * 100 if start_balance else 0.0

    # Calculate daily P&L
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daily_pnl = sum(
        t["pnl"] for t in trades
        if isinstance(t.get("timestamp"), str) and t["timestamp"].startswith(today)
    )

    # Display top metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current Balance", f"${capital:.2f}")
    col2.metric("Total Return", f"{total_return_pct:.2f}%")
    col3.metric("Daily P&L", f"${daily_pnl:.2f}")
    col4.metric("Win Rate", f"{trading_engine.calculate_win_rate(trades)}%")

    st.markdown("---")

    # Assets performance visualization
    left, right = st.columns([2, 1])
    with left:
        st.subheader("📈 Assets Analysis")
        if trades:
            fig = dashboard.create_detailed_performance_chart(trades, capital)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No trade data available yet.")

    with right:
        st.subheader("📊 Trade Stats")
        if trades:
            stats = trading_engine.calculate_trade_statistics(trades)
            dashboard.display_trade_statistics(stats)
        else:
            st.info("No trade data available.")

    st.subheader("🔄 Recent Trades")
    if trades:
        dashboard.display_trades_table(trades)
    else:
        st.info("No trades executed yet.")
