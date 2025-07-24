import streamlit as st

def render(trading_engine, dashboard):
    st.title("📈 Market Analysis")

    try:
        # Fetch symbol list from BybitClient
        symbol_response = trading_engine.client.get_symbols()
        if isinstance(symbol_response, dict) and "result" in symbol_response:
            symbols = [item["name"] for item in symbol_response["result"]]
        elif isinstance(symbol_response, list):
            symbols = [item["symbol"] for item in symbol_response]
        else:
            st.warning("Unexpected symbol format from API.")
            symbols = []
    except Exception as e:
        st.error(f"Error fetching symbols: {e}")
        return

    selected = st.selectbox("Select Symbol", symbols) if symbols else None

    if selected:
        col1, col2, col3 = st.columns(3)
        with col1:
            timeframe = st.selectbox("Timeframe", ["15m", "1h", "4h", "1d"], index=1)
        with col2:
            limit = st.slider("Candles", 50, 500, 100)
        with col3:
            indicators = st.multiselect(
                "Indicators",
                ["EMA 9", "EMA 21", "MA 50", "MA 200", "Bollinger Bands",
                 "RSI", "MACD", "Stoch RSI", "Volume"],
                default=["Bollinger Bands", "MA 200", "RSI", "Volume"]
            )

        with st.spinner("Loading chart data…"):
            try:
                # Fallback to client.get_kline() if get_chart_data is not implemented
                if hasattr(trading_engine.client, "get_chart_data"):
                    data = trading_engine.client.get_chart_data(selected, timeframe, limit)
                else:
                    data = trading_engine.client.get_kline(selected, interval=timeframe, limit=limit)
            except Exception as e:
                st.error(f"Error fetching chart data: {e}")
                return

            if data:
                fig = dashboard.create_technical_chart(data, selected, indicators)
                st.plotly_chart(fig, use_container_width=True)

                current = [
                    s for s in trading_engine.get_recent_signals()
                    if s["symbol"] == selected
                ]
                if current:
                    st.subheader(f"🎯 Current Signals for {selected}")
                    for s in current:
                        dashboard.display_signal_card(s)
            else:
                st.error(f"⚠️ No data returned for {selected}")
