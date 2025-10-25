# main.py - Core trading bot logic (corrected client setup)
import time
import threading
import queue
import logging
import pandas as pd
import os
from alpaca.trading.client import TradingClient
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoLatestQuoteRequest, CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta
from config import *

# Setup logging
logging.basicConfig(filename=LOG_FILE, level=getattr(logging, LOG_LEVEL),
                    format='%(asctime)s - %(levelname)s - %(message)s')
console = logging.StreamHandler()
console.setLevel(getattr(logging, LOG_LEVEL))
logging.getLogger('').addHandler(console)

# Add dedicated error log file (only for ERROR/CRITICAL levels—to easily check script issues while running) # STRATEGY TWEAK: No impact on trading; tweak if you want a different filename or level (e.g., WARNING for more details).
error_handler = logging.FileHandler('errors.log')
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger('').addHandler(error_handler)

# Initialize Alpaca clients (paper trading)
trading_client = TradingClient(ALPACA_PAPER_KEY, ALPACA_PAPER_SECRET, paper=True)  # For orders and positions
data_client = CryptoHistoricalDataClient(ALPACA_PAPER_KEY, ALPACA_PAPER_SECRET)  # For prices and bars (keys for higher rate limits)

# Global state
positions = {}
trade_queue = queue.Queue()
last_trade = {symbol: 0 for symbol in SYMBOLS}
daily_pnl = 0
current_prices = {symbol: None for symbol in SYMBOLS}  # Track latest prices for all symbols
price_history = {symbol: [] for symbol in SYMBOLS}  # For momentum calculations

# Helper to normalize symbols (Alpaca positions use "BTCUSD" without slash—note: orders (buy/sell) require "BTC/USD" with slash)
def normalize_symbol(symbol):
    return symbol.replace("/", "")

def fetch_prices():
    """Fetch real-time prices from Alpaca in a thread."""
    while True:
        try:
            request = CryptoLatestQuoteRequest(symbol_or_symbols=SYMBOLS)
            quotes = data_client.get_crypto_latest_quote(request)
            for symbol in SYMBOLS:
                quote = quotes[symbol]
                price = (quote.ask_price + quote.bid_price) / 2 if quote else None  # Use mid-price for fairness
                trade_queue.put((symbol, price))
            logging.info(f"Fetched prices for {', '.join(SYMBOLS)}")
        except Exception as e:
            logging.error(f"Price fetch failed: {e}")
        time.sleep(CHECK_INTERVAL)

def calculate_atr(symbol):
    """Calculate proper 14-period ATR using 1-min bars from Alpaca."""
    try:
        request = CryptoBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Minute,
            start=datetime.now() - timedelta(minutes=20),  # Fetch extra for safety
            limit=15  # Enough for 14 periods
        )
        bars = data_client.get_crypto_bars(request)
        if symbol not in bars or len(bars[symbol]) < 14:
            return ATR_MIN  # Default if not enough data

        # Convert to DataFrame for TR calculation
        df = pd.DataFrame([{
            'high': b.high,
            'low': b.low,
            'close': b.close
        } for b in bars[symbol]])
        df['prev_close'] = df['close'].shift(1)
        df['tr'] = df['high'] - df['low']
        df['tr'] = df.apply(lambda row: max(row['tr'], abs(row['high'] - row['prev_close']), abs(row['low'] - row['prev_close'])) if pd.notnull(row['prev_close']) else row['tr'], axis=1)
        return df['tr'].tail(14).mean()
    except Exception as e:
        logging.error(f"ATR calculation failed for {symbol}: {e}")
        return ATR_MIN

def trade_logic():
    """Main trading loop."""
    global daily_pnl
    asset_map = {normalize_symbol(s): s for s in SYMBOLS}  # Map "BTCUSD" -> "BTC/USD" (handles position symbols without slash for sells)
    while True:
        try:
            symbol, current_price = trade_queue.get(timeout=CHECK_INTERVAL)
            if current_price is None:
                continue

            # Update current prices and history
            current_prices[symbol] = current_price
            price_history[symbol].append(current_price)
            if len(price_history[symbol]) > 50:  # Keep last 50 data points
                price_history[symbol].pop(0)

            atr = calculate_atr(symbol)

            # Calculate percent_gain first (for no_buy checks)
            percent_gain = (current_price - price_history[symbol][-2]) / price_history[symbol][-2] if len(price_history[symbol]) > 1 else 0

            # Buy logic
            if current_price > 0:
                cooldown_time = (datetime.now() - datetime.fromtimestamp(last_trade[symbol])).total_seconds()
                current_investment = sum(float(pos.cost_basis) for pos in trading_client.get_all_positions() if pos.symbol == normalize_symbol(symbol))
                if (cooldown_time > MIN_TRADE_COOLDOWN and
                    atr > ATR_MIN and
                    current_investment < MAX_INVESTMENT and
                    percent_gain >= GAIN_THRESHOLD):
                    qty = POSITION_SIZE / current_price
                    trading_client.submit_order(symbol=symbol, qty=qty, side='buy', type='market', time_in_force='gtc')
                    last_trade[symbol] = time.time()
                    logging.info(f"Bought {qty} {symbol} at ${current_price}")
                    # Log to CSV (added reason=None for trades)
                    with open(TRADE_LOG_FILE, 'a') as f:
                        f.write(f"{datetime.now()},buy,{symbol},{current_price},{qty},{daily_pnl},\n")
                elif percent_gain >= GAIN_THRESHOLD:  # Log no_buy only if gain met but others failed (avoids spam) # STRATEGY TWEAK: Edit conditions here to log more/less reasons; helps debug why no trades in flat markets.
                    reason = []
                    if cooldown_time <= MIN_TRADE_COOLDOWN:
                        reason.append("Cooldown active")
                    if atr <= ATR_MIN:
                        reason.append("Low volatility (ATR)")
                    if current_investment >= MAX_INVESTMENT:
                        reason.append("Max investment reached")
                    if reason:
                        logging.info(f"No buy for {symbol}: {', '.join(reason)}")
                        # Log to CSV with action='no_buy' and reason
                        with open(TRADE_LOG_FILE, 'a') as f:
                            f.write(f"{datetime.now()},no_buy,{symbol},{current_price},0,{daily_pnl},{', '.join(reason)}\n")

            # Sell logic (check open positions)
            for pos in trading_client.get_all_positions():
                if pos.symbol in asset_map:
                    trade_symbol = asset_map[pos.symbol]
                    curr_price = current_prices.get(trade_symbol)
                    if curr_price is None:
                        continue
                    entry_price = float(pos.cost_basis) / float(pos.qty)
                    profit_percent = (curr_price - entry_price) / entry_price - FEE_PERCENT
                    if profit_percent >= TAKE_PROFIT or profit_percent <= -LOSS_THRESHOLD:
                        trading_client.submit_order(symbol=trade_symbol, qty=pos.qty, side='sell', type='market', time_in_force='gtc')
                        pnl = (curr_price - entry_price) * float(pos.qty) - (FEE_PERCENT * entry_price * float(pos.qty))
                        daily_pnl += pnl
                        logging.info(f"Sold {pos.qty} {trade_symbol} at ${curr_price}, PNL: ${pnl:.2f}, Daily PNL: ${daily_pnl:.2f}")
                        # Log to CSV (added reason=None for trades)
                        with open(TRADE_LOG_FILE, 'a') as f:
                            f.write(f"{datetime.now()},sell,{trade_symbol},{curr_price},{pos.qty},{daily_pnl},\n")

            # Risk management
            if daily_pnl < DAILY_LOSS_LIMIT:
                logging.critical("Daily loss limit hit—stopping bot")
                break

        except Exception as e:
            logging.error(f"Trade logic error: {e}")
        time.sleep(1)  # Prevent tight loop

if __name__ == "__main__":
    # Start price fetch thread
    price_thread = threading.Thread(target=fetch_prices, daemon=True)
    price_thread.start()

    # Start trade logic
    trade_logic()