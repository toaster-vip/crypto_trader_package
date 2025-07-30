# notifier.py
import requests
from config import SERVER_CHAN_KEY

def send_serverchan_notification(title: str, content: str):
    """
    通过 Server 酱发送通知
    """
    if not SERVER_CHAN_KEY:
        print("[通知] ❌ Server酱 KEY 未配置，跳过发送通知")
        return

    url = f"https://sctapi.ftqq.com/{SERVER_CHAN_KEY}.send"
    data = {
        "title": title,
        "desp": content
    }

    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print("📬 通知已发送")
        else:
            print(f"[通知] ❌ 发送失败: {response.status_code}")
    except Exception as e:
        print(f"[通知] ❌ 异常: {e}")