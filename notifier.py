import requests
from config import CONFIG

def send_notification(message):
    key = CONFIG.get("SERVER_CHAN_KEY")
    if key:
        requests.get(f"https://sctapi.ftqq.com/{key}.send", params={"title":"Trade Notification", "desp": message})