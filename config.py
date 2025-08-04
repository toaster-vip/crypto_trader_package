import os

CONFIG = {
    # ==== 账户与敏感信息 ====
    "KUCOIN_API_KEY": os.getenv("KUCOIN_API_KEY"),
    "KUCOIN_API_SECRET": os.getenv("KUCOIN_API_SECRET"),
    "KUCOIN_API_PASSPHRASE": os.getenv("KUCOIN_API_PASSPHRASE"),
    "SERVER_CHAN_KEY": os.getenv("SERVER_CHAN_KEY"),

    # ==== 日志和运行参数 ====
    "LOG_DIR": "trade_logs",
    "SIM_START_BALANCE": 100,           # 模拟盘初始资金
    "SIMULATE": False,                  # False=实盘，True=模拟盘
    "GIT_BRANCH": "main",               # 默认Git分支

    # ==== 资金分配与风控 ====
    "MAX_POSITION_RATIO": 0.10,         # 每币最大仓位比例
    "MIN_TURNOVER_1H": 5000,            # 最低1小时成交额过滤
    "MAX_WORKERS": 10,                  # 多线程最大数量
    "WORKER_SLEEP": 0.18,               # 多线程sleep间隔（秒）
    "TOP_N": 5,                         # 评分最高币数
    "USDT_STEP": 0.01,                  # USDT最小交易单位
    "MIN_BUY_AMOUNT": 5,                # 最小买入金额
    "AMOUNT_PREC": 0.00000001,          # 数量小数精度

    # ==== 策略因子参数 ====
    "RSI_PERIOD": 14,                   # RSI周期
    "MA_SHORT": 5,                      # MA短周期
    "MA_LONG": 20,                      # MA长周期
    "CCI_PERIOD": 20,                   # CCI周期
    "CCI_DENOM": 0.015,                 # CCI分母
    "KDJ_COM": 2,                       # KDJ指数平滑
    "MOMENTUM_WIN": 10,                 # 动量均值窗口
    "VOLUME_WIN": 20,                   # 成交量均值窗口
    "NUM_STD": 2,                       # BOLL通道标准差倍数
    "EPS": 1e-6,                        # 防除零极小量
    "MIN_KLINE_ROWS": 30,               # 最小K线行数
    "MAX_RETRIES": 3,                   # K线获取最大重试

    # ==== 风险&策略逻辑 ====
    "TAKE_PROFIT": 0.05,                # 止盈线 5%
    "STOP_LOSS": -0.03,                 # 止损线 -3%
    "TRAILING_STOP_PCT": 0.03,          # 移动止损比例
    "COOLDOWN_AFTER_LOSS": 3,           # 止损后冷却轮数
    "NEW_COIN_VOLUME": 50,              # 新币判定成交量
    "EXTREME_PCT_THRESHOLD": 0.3,       # 极端行情阈值

    # ==== 费用相关 ====
    "FEE_RATE": 0.00075,                # 模拟盘手续费率

    # ==== 模拟滑点 ====
    "SIM_SLIPPAGE_PCT": 0.0003,         # 默认滑点0.03%
    "DRY_RUN": False                    #  True=只演练, False=真下单
}

# --- 兼容旧代码 ---
TRADE = {
    "TAKE_PROFIT": CONFIG["TAKE_PROFIT"],
    "STOP_LOSS": CONFIG["STOP_LOSS"],
}
STRATEGY = {}  # 如需扩展，可单独写入策略相关dict
LOG_DIR = CONFIG["LOG_DIR"]
SERVER_CHAN_KEY = CONFIG.get("SERVER_CHAN_KEY", None)

# 推荐后续所有参数都用 CONFIG["xxx"] 读取！