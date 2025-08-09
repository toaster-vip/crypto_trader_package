# notifier.py
import os
import requests
from config import CONFIG

def send_serverchan_notification(title: str, content: str):
    """
    通过 Server 酱发送通知
    使用 CONFIG['SERVER_CHAN_KEY'] 或环境变量 SERVER_CHAN_KEY
    """
    key = (CONFIG.get("SERVER_CHAN_KEY") or os.getenv("SERVER_CHAN_KEY") or "").strip()
    if not key:
        print("[通知] ❌ Server酱 KEY 未配置（CONFIG['SERVER_CHAN_KEY'] 或环境变量 SERVER_CHAN_KEY），跳过发送")
        return

    url = f"https://sctapi.ftqq.com/{key}.send"
    data = {
        "title": title,
        "desp": content
    }

    try:
        resp = requests.post(url, data=data, timeout=10)
        if resp.status_code == 200:
            print("📬 通知已发送")
        else:
            print(f"[通知] ❌ 发送失败: HTTP {resp.status_code} | {resp.text[:200]}")
    except Exception as e:
        print(f"[通知] ❌ 异常: {e}")