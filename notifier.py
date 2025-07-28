import requests
from config import SERVER_CHAN_KEY

def send_wechat_notification(title: str, content: str):
    if not SERVER_CHAN_KEY:
        print("[WARN] Server酱 KEY 未配置，跳过通知")
        return

    url = f"https://sctapi.ftqq.com/{SERVER_CHAN_KEY}.send"
    data = {
        "title": title,
        "desp": content
    }

    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print(f"[INFO] Server酱通知发送成功：{title}")
        else:
            print(f"[WARN] Server酱请求失败，状态码：{response.status_code}")
    except Exception as e:
        print(f"[ERROR] Server酱通知异常：{e}")