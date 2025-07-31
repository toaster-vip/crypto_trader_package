import os

CONFIG = {
    # ====== 账户与敏感信息（环境变量注入，安全第一） ======
    "KUCOIN_API_KEY": os.getenv("KUCOIN_API_KEY"),         # KuCoin API KEY，强烈建议用环境变量
    "KUCOIN_API_SECRET": os.getenv("KUCOIN_API_SECRET"),   # KuCoin API SECRET，环境变量注入
    "KUCOIN_API_PASSPHRASE": os.getenv("KUCOIN_API_PASSPHRASE"),  # KuCoin API PASSPHRASE
    "SERVER_CHAN_KEY": os.getenv("SERVER_CHAN_KEY"),       # Server酱通知KEY，推送重大事件/盈亏报告

    # ====== 运行/日志参数 ======
    "SIMULATE": True,                        # True=模拟模式（无真实下单），False=实盘
    "LOG_DIR": "/home/linuxuser/trade_logs/", # 日志存储路径，建议SSD盘

    # ====== 资金分配与风控 ======
    "RESERVE_RATIO": 0.12,      # ⚠️ 保留资金比例（不动用全部资金，防极端行情/手续费/应急，建议10-15%）
    
    # ====== 策略参数（专业分权重）======
    "STRATEGY": {
        "MACD_WEIGHT": 0.18,           # 强化趋势反转识别
        "RSI_WEIGHT": 0.12,            # 超买超卖信号，配合趋势
        "SMA_WEIGHT": 0.09,            # 简单均线，捕捉中线趋势
        "MOMENTUM_WEIGHT": 0.09,       # 动量爆发，筛选短线活跃
        "TREND_WEIGHT": 0.08,          # 长趋势信号，分散风险
        "ADX_WEIGHT": 0.08,            # 趋势强度，避免震荡入场
        "OBV_WEIGHT": 0.08,            # 主力资金流量
        "CCI_WEIGHT": 0.06,            # 商品通道，防假信号
        "KDJ_WEIGHT": 0.05,            # 高频波动，捕捉短波段
        "SAR_WEIGHT": 0.05,            # 止盈止损辅助判断
        "BOLLINGER_WEIGHT": 0.05,      # 布林带，分散极端波动
        "VOLUME_WEIGHT": 0.07          # 量能确认，有量才有价
    },

    # ====== 单币种风险限制 ======
    "MAX_POSITION_RATIO": 0.18,  # 单币最大可投入资金比例（18%，防止爆仓），建议15-20%区间

    # ====== 调仓及风控高级参数 ======
    "TRADE": {
        "TAKE_PROFIT": 0.048,         # 止盈：+4.8%，滚动浮动止盈，适合近期波动行情
        "STOP_LOSS": -0.022           # 止损：-2.2%，严格止损优先生存
    },

    "REBALANCE": {
        "HOLD_THRESHOLD_RANK": 8,         # 当前持仓仍在评分前8名，继续持有，不主动换仓
        "SCORE_DIFF_THRESHOLD": 0.13,     # 新推荐币分数比当前币高13%才调仓，降低换手率
        "REQUIRE_CONSISTENT_ROUNDS": 2    # 新币需连续2轮进Top再买入，过滤假突破
    },

    # ====== 批量调度与实盘运行优化 ======
    "RUN_MODE": {
        "TEST_MODE": False,          # False=正式实盘，True=仅分析不下单
        "BATCH_SIZE": 25,            # 每批并发分析25个币，兼顾性能与API速率
        "MAX_WORKERS": 6,            # 6线程并发，防止服务器爆栈
        "BATCH_DELAY": 1,            # 每批分析延迟1秒，防API限速
        "REPORT_INTERVAL": 200       # 每200轮推送一次盈亏报告
    }
}

# 保持兼容性（所有老代码无缝调用）
KUCOIN_API_KEY = CONFIG["KUCOIN_API_KEY"]
KUCOIN_API_SECRET = CONFIG["KUCOIN_API_SECRET"]
KUCOIN_API_PASSPHRASE = CONFIG["KUCOIN_API_PASSPHRASE"]
SIMULATE = CONFIG["SIMULATE"]
SERVER_CHAN_KEY = CONFIG["SERVER_CHAN_KEY"]
TRADE = CONFIG["TRADE"]
STRATEGY = CONFIG["STRATEGY"]
LOG_DIR = CONFIG["LOG_DIR"]