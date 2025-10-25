# dashboard.py - Streamlit dashboard for visualizing bot performance
import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
from config import TRADE_LOG_FILE, SYMBOLS, ALPACA_PAPER_KEY, ALPACA_PAPER_SECRET, CHECK_INTERVAL
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoLatestQuoteRequest, CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame

# Initialize Alpaca data client for live fetches
data_client = CryptoHistoricalDataClient(ALPACA_PAPER_KEY, ALPACA_PAPER_SECRET)

st.title(f"Crypto Trading Bot Dashboard - {datetime.now().strftime('%b %d, %Y')}")

# Load trade data (updated for new 'reason' column)
if os.path.exists(TRADE_LOG_FILE):
    df = pd.read_csv(TRADE_LOG_FILE, names=['timestamp', 'action', 'symbol', 'price', 'qty', 'daily_pnl', 'reason'])
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    st.write("### Trade History", df)

    # P&L over time (line chart)
    st.subheader("Profit & Loss Over Time")
    st.line_chart(df.set_index('timestamp')['daily_pnl'])

    # Positions summary (bar chart of net open quantity)
    st.subheader("Open Positions")
    df['signed_qty'] = df['qty'].where(df['action'] == 'buy', -df['qty'])
    open_positions = df.groupby('symbol')['signed_qty'].sum().clip(lower=0)
    st.bar_chart(open_positions)

    # Daily PNL status
    st.subheader("Daily PNL")
    latest_pnl = df['daily_pnl'].iloc[-1] if not df.empty else 0
    st.metric("Current Daily PNL", f"${latest_pnl:.2f}")

    # New: Reasons why no buy (show last 10 no_buy entries)
    st.subheader("Recent No-Buy Reasons")
    no_buy_df = df[df['action'] == 'no_buy'].tail(10)[['timestamp', 'symbol', 'reason']]
    if not no_buy_df.empty:
        st.table(no_buy_df)
    else:
        st.write("No missed buy opportunities logged yet.")

else:
    st.write("No trade data yet—start the bot!")

# New: Live Market Data for the 4 symbols
st.subheader("Live Market Data")
try:
    # Fetch latest quotes for current prices and 24h volume
    quote_request = CryptoLatestQuoteRequest(symbol_or_symbols=SYMBOLS)
    quotes = data_client.get_crypto_latest_quote(quote_request)

    # Fetch 1-day bars for 24h % change (close from 24h ago to now)
    bar_request = CryptoBarsRequest(
        symbol_or_symbols=SYMBOLS,
        timeframe=TimeFrame.Day,
        start=datetime.now() - timedelta(days=2),  # Extra for safety
        limit=2
    )
    bars = data_client.get_crypto_bars(bar_request)

    # Fetch recent 1-min bar for % since last check (approx CHECK_INTERVAL seconds ago)
    min_bar_request = CryptoBarsRequest(
        symbol_or_symbols=SYMBOLS,
        timeframe=TimeFrame.Minute,
        start=datetime.now() - timedelta(minutes=2),  # Approx for 45s interval
        limit=2
    )
    min_bars = data_client.get_crypto_bars(min_bar_request)

    live_data = []
    for symbol in SYMBOLS:
        quote = quotes.get(symbol, {})
        current_price = (quote.ask_price + quote.bid_price) / 2 if quote else None
        # Fix: Access bars using dict-like [] instead of .get() (CryptoBars supports __getitem__, not always .get()) # No strategy tweak: This is just API compatibility—edit if your alpaca-py version differs.
        symbol_bars = bars[symbol] if symbol in bars else []
        volume_24h = symbol_bars[-1].volume if symbol_bars else None

        # 24h % change
        pct_24h = ((current_price - symbol_bars[0].close) / symbol_bars[0].close * 100) if len(symbol_bars) > 1 and current_price else 0

        # % since last checked (from prev 1-min close)
        symbol_min_bars = min_bars[symbol] if symbol in min_bars else []
        pct_since_last = ((current_price - symbol_min_bars[0].close) / symbol_min_bars[0].close * 100) if len(symbol_min_bars) > 1 and current_price else 0

        live_data.append({
            'Symbol': symbol,
            'Current Price': f"${current_price:.4f}" if current_price else "N/A",
            '% Change Since Last Check (~45s)': f"{pct_since_last:.2f}%" if current_price else "N/A",
            '24h % Change': f"{pct_24h:.2f}%",
            '24h Volume': f"{volume_24h:,.0f}" if volume_24h else "N/A"
        })

    st.table(pd.DataFrame(live_data))
except Exception as e:
    st.write(f"Error fetching live data: {e}")

# Run locally: streamlit run dashboard.py
# Deploy to Streamlit Cloud: Push to GitHub, connect at share.streamlit.io