import requests
from config import CONFIG

def send_notification(message):
    print("[DEBUG] 我从 iPad 修改了代码！This is 2nd test")
    key = CONFIG.get("SERVER_CHAN_KEY")
    if key:
        requests.get(f"https://sctapi.ftqq.com/{key}.send", params={"title":"Trade Notification", "desp": message})