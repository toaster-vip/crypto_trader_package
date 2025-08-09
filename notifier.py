# notifier.py
import os
import requests
from config import CONFIG

def _mask(s: str, head=3, tail=3):
    if not s:
        return ""
    if len(s) <= head + tail:
        return "*" * len(s)
    return f"{s[:head]}***{s[-tail:]}"

def get_server_chan_key() -> str:
    # 先 CONFIG，后环境变量（两路兜底）
    key = (CONFIG.get("SERVER_CHAN_KEY") or "").strip()
    if not key:
        key = (os.getenv("SERVER_CHAN_KEY") or "").strip()
    return key

def send_serverchan_notification(title: str, content: str):
    """
    通过 Server 酱发送通知（SCT 新版）
    """
    key = get_server_chan_key()
    if not key:
        print("[通知] ❌ Server酱 KEY 未配置（CONFIG['SERVER_CHAN_KEY'] 或环境变量 SERVER_CHAN_KEY），跳过发送")
        return

    # 简单限长，避免超大日志
    content = content if len(content) < 8000 else (content[:7800] + "\n\n[...截断，过长...]")

    url = f"https://sctapi.ftqq.com/{key}.send"
    data = {"title": title, "desp": content}

    try:
        resp = requests.post(url, data=data, timeout=10)
        if resp.status_code == 200:
            print(f"📬 通知已发送（key={_mask(key)}）")
        else:
            print(f"[通知] ❌ 发送失败: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        print(f"[通知] ❌ 异常: {e}")