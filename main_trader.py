#!/usr/bin/env python3
import os
os.makedirs("/home/linuxuser/trade_logs", exist_ok=True)
import logging
from config import CONFIG
from api import get_market_data
from strategy import calculate_signal
from trade_manager import execute_trade
from notifier import send_notification
from datetime import datetime

def main():
    log_path = f"/home/linuxuser/trade_logs/trade_{datetime.now().date()}.log"
    logging.basicConfig(filename=log_path, level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    #logging.basicConfig(filename=f"trade_logs/trade_{datetime.now().date()}.log", level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    for symbol in CONFIG['SYMBOLS']:
        logging.info(f"Processing symbol: {symbol}")
        data = get_market_data(symbol)
        signal = calculate_signal(symbol, data)
        execute_trade(symbol, data, signal)
    send_notification("Trade run completed.")

if __name__ == "__main__":
    main()
