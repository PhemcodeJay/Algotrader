import streamlit as st
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db import db_manager, Signal

def render(trading_engine, dashboard, db_manager):
    st.title("📊 AI Trading Signals")

    col1, col2, col3 = st.columns(3)
    with col1:
        symbol_limit = st.number_input("Symbols to Analyze", min_value=10, max_value=100, value=30)
    with col2:
        confidence_threshold = st.slider("Min Confidence %", 50, 95, 75)
    with col3:
        if st.button("🔍 Scan New Signals", type="secondary"):
            with st.spinner("Analyzing markets..."):
                signals = trading_engine.generate_signals(confidence_threshold)
                st.success(f"Generated {len(signals)} signals")
                st.rerun()

    with db_manager.get_session() as session:
        signal_objs = session.query(Signal) \
                             .order_by(Signal.created_at.desc()) \
                             .limit(100).all()
        signals = [s.__dict__ for s in signal_objs]

    # Optional: render the signals table
    if signals:
        st.subheader("🧠 Recent AI Signals")
        st.dataframe(signals)


    if signals:
        col1, col2, col3 = st.columns(3)
        with col1:
            strategy_filter = st.multiselect(
                "Filter by Strategy",
                options=sorted({s["strategy"] for s in signals}),
                default=sorted({s["strategy"] for s in signals})
            )
        with col2:
            side_filter = st.multiselect("Filter by Side", ["LONG", "SHORT"], default=["LONG", "SHORT"])
        with col3:
            min_score = st.slider("Minimum Score", 70, 100, 80)

        filtered = [
            s for s in signals
            if s["strategy"] in strategy_filter
            and s["side"] in side_filter
            and s["score"] >= min_score
        ]

        st.subheader(f"📡 {len(filtered)} Active Signals")

        if filtered:
            dashboard.display_signals_table(filtered)
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("📤 Export to Discord"):
                    for s in filtered[:5]:
                        trading_engine.post_signal_to_discord(s)
                    st.success("Posted top 5 to Discord!")
            with col2:
                if st.button("📤 Export to Reddit"):
                    for s in filtered[:5]:
                        trading_engine.post_signal_to_reddit(s)
                    st.success("Posted top 5 to Reddit!")
            with col3:
                if st.button("📄 Export PDF"):
                    path = trading_engine.export_signals_pdf(filtered)
                    st.success(f"PDF saved to {path}")
        else:
            st.info("No signals match the current filters.")
    else:
        st.info("No signals available. Scan to generate signals.")
