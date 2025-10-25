# config.py - Configuration settings for the crypto trading bot
# Adjust these values to tweak the strategy (all in USD unless noted)
# API keys are now loaded from .env file using python-dotenv

from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()
ALPACA_PAPER_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_PAPER_SECRET = os.getenv("ALPACA_API_SECRET")

# Exchange and API settings
BASE_URL = "https://paper-api.alpaca.markets"  # Paper trading endpoint

# Trading parameters
SYMBOLS = ["BTC/USD", "ETH/USD", "XRP/USD", "SOL/USD"]  # Symbols in Alpaca format; add more later (e.g., "SHIB/USD", "AVAX/USD") # STRATEGY TWEAK: Choose volatile ones like DOGE/SOL for potential quick gains with small $; edit to swap for less risky if losses mount.
CHECK_INTERVAL = 45  # Seconds between price checks (tweak: 30 for faster, 60 for slower) # STRATEGY TWEAK: Shorter intervals increase responsiveness but may lead to more frequent trades and API calls.
GAIN_THRESHOLD = 0.001  # 0.1% price increase to buy (tweak: 0.005 for 0.5% more conservative) # STRATEGY TWEAK: Higher threshold reduces false positives from noise but might miss quick momentum.
POSITION_SIZE = 150  # $200 per trade (tweak: 100 for smaller, 500 for larger) # STRATEGY TWEAK: Smaller sizes reduce risk per trade; larger can amplify gains but also losses.
MAX_INVESTMENT = 900  # Max total invested (tweak: 1000 for less risk) # STRATEGY TWEAK: Lower this to cap overall exposure; higher allows more positions but increases drawdown risk.
FEE_PERCENT = 0.002  # 0.2% trading fee (Alpaca's approx.; tweak if exchange changes) # STRATEGY TWEAK: Adjust based on actual fees; higher fees make the bot more conservative in profit calcs.
MIN_TRADE_COOLDOWN = 30  # Seconds cooldown per symbol (tweak: 15 for faster, 60 for slower) # STRATEGY TWEAK: Longer cooldown prevents over-trading in volatile periods.
ATR_MIN = 0.00005  # Minimum ATR for volatility (tweak: 0.0001 for stricter) # STRATEGY TWEAK: With proper bar-based ATR now, this might need recalibration (e.g., for BTC 1-min ATR, try 10-50 USD based on backtesting).

# Risk management
LOSS_THRESHOLD = 0.03  # 3% loss to sell (tweak: 0.02 for tighter, 0.05 for looser) # STRATEGY TWEAK: Tighter stops protect capital but may exit winners early; looser allows more room but risks bigger losses.
TAKE_PROFIT = 0.05  # 5% profit to sell (tweak: 0.03 for quicker, 0.10 for higher) # STRATEGY TWEAK: Lower for quick profits in choppy markets; higher to capture trends but risks giving back gains.
DAILY_LOSS_LIMIT = -200  # Stop trading if daily loss hits this (tweak: -200 for less risk) # STRATEGY TWEAK: Stricter limit halts sooner to preserve capital.

# Logging and data
LOG_FILE = "bot_log_{}.log".format(__import__('datetime').datetime.now().strftime("%Y-%m-%d"))
LOG_LEVEL = "INFO"  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL (tweak for verbosity)
TRADE_LOG_FILE = "trades.csv"  # CSV for dashboard data

# Verify keys are loaded (for debugging)
if not ALPACA_PAPER_KEY or not ALPACA_PAPER_SECRET:
    raise ValueError("Alpaca API keys not found in .env file. Check your .env setup.")