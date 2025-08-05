# log_utils.py
import os
import pandas as pd
from datetime import datetime

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

def log_snapshot(balances, price_map, tag="snapshot", date_str=None):
    """
    资产快照记录，含每币种数量、价格、市值。
    tag: "before" | "after" | "periodic"
    """
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    rows = []
    total_value = 0
    for symbol, info in balances.items():
        if isinstance(info, dict):
            amount = float(info.get("amount", 0))
        else:
            amount = float(info)
        price = float(price_map.get(symbol, 0))
        value = amount * price
        rows.append({
            "币种": symbol,
            "数量": amount,
            "现价": price,
            "市值": value,
            "快照类型": tag,
            "时间": date_str
        })
        total_value += value
    df = pd.DataFrame(rows)
    # 总价值也附加一行
    df.loc[len(df)] = ["总计", "", "", total_value, tag, date_str]
    filename = os.path.join(LOG_DIR, f"{date_str}_{tag}_account_snapshot.csv")
    df.to_csv(filename, index=False, encoding="utf-8-sig")
    print(f"[LOG] 已保存账户快照: {filename}")

def log_trade_detail(trade_detail, date_str=None):
    """
    记录每笔交易的详细流水。trade_detail: dict。
    """
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    df = pd.DataFrame([trade_detail])
    filename = os.path.join(LOG_DIR, f"{date_str}_trade_detail.csv")
    # 如果已存在则追加，否则新建
    if os.path.exists(filename):
        df.to_csv(filename, mode="a", index=False, header=False, encoding="utf-8-sig")
    else:
        df.to_csv(filename, index=False, encoding="utf-8-sig")
    print(f"[LOG] 已保存交易流水: {filename}")

def log_summary(summary_data, date_str=None):
    """
    汇总分析结果，如盈亏汇总、资产变化等。
    """
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
    df = pd.DataFrame([summary_data])
    filename = os.path.join(LOG_DIR, f"{date_str}_summary.csv")
    if os.path.exists(filename):
        df.to_csv(filename, mode="a", index=False, header=False, encoding="utf-8-sig")
    else:
        df.to_csv(filename, index=False, encoding="utf-8-sig")
    print(f"[LOG] 已保存汇总: {filename}")