#!/bin/bash

# ========= 路径配置 =========
PROJECT_DIR="/home/linuxuser/crypto_trader_package"
VENV_DIR="/home/linuxuser/taenv"
LOCKFILE="/tmp/crypto_trader_lockfile"
LOGFILE="/home/linuxuser/trade_logs/cron.log"
SERVER_CHAN_KEY="SCT290772THBFAsWEtLa29M3l98qRSZ1DZ"  # ← 修改为你自己的 Server酱 Key

# ========= 锁文件防并发 =========
if [ -e "$LOCKFILE" ]; then
    echo "[WARN] 🚫 上一个进程尚未完成，跳过本轮执行。" | tee -a "$LOGFILE"
    exit 1
fi
touch "$LOCKFILE"

# ========= 启动日志 =========
start_time=$(date +%s)
echo "" >> "$LOGFILE"
echo "[INFO] 🚀 开始执行 run_once.sh at $(date)" | tee -a "$LOGFILE"

# ========= 激活虚拟环境 =========
echo "[INFO] ✅ 激活虚拟环境：$VENV_DIR" | tee -a "$LOGFILE"
source "$VENV_DIR/bin/activate"

# ========= 进入项目目录 =========
cd "$PROJECT_DIR" || {
    echo "[ERROR] ❌ 无法进入项目目录 $PROJECT_DIR" | tee -a "$LOGFILE"
    rm -f "$LOCKFILE"
    exit 1
}

# ========= 拉取 Git 最新代码 =========
echo "[INFO] 🔄 尝试拉取 Git 最新代码..." | tee -a "$LOGFILE"
if ! git pull --rebase; then
    echo "[ERROR] ❌ Git 拉取失败，跳过执行。" | tee -a "$LOGFILE"
    rm -f "$LOCKFILE"
    exit 1
fi

# ========= 执行主交易程序 =========
echo "[INFO] ▶️ 执行 main_trader.py..." | tee -a "$LOGFILE"
if ! python main_trader.py >> "$LOGFILE" 2>&1; then
    echo "[ERROR] ❌ main_trader.py 执行失败！" | tee -a "$LOGFILE"
fi

# ========= 清除锁文件 & 统计时间 =========
rm -f "$LOCKFILE"
end_time=$(date +%s)
elapsed=$((end_time - start_time))

echo "[INFO] ✅ 本轮执行完毕 at $(date)，耗时 ${elapsed}s" | tee -a "$LOGFILE"

# ========= Server酱通知（可选） =========
# 仅在启用时发送通知，可以加个判断开关
ENABLE_NOTIFY=true

if [ "$ENABLE_NOTIFY" = true ]; then
    curl -s -X POST "https://sctapi.ftqq.com/$SERVER_CHAN_KEY.send" \
        -d "title=✅ 自动交易已完成" \
        -d "desp=本轮执行耗时：${elapsed} 秒，时间：$(date '+%Y-%m-%d %H:%M:%S')" > /dev/null
fi