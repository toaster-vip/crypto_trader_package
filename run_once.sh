#!/bin/bash

# ========== 配置 ==========
PROJECT_DIR="/home/linuxuser/crypto_trader_package"
VENV_DIR="/home/linuxuser/taenv"
LOCKFILE="/tmp/crypto_trader_lockfile"
LOG_DIR="/home/linuxuser/trade_logs"
MAX_RUNTIME=600  # 最大允许 main_trader.py 运行时间（秒）
LOGFILE="$LOG_DIR/cron_runonce_$(date '+%Y%m%d').log"

# ========== 函数：日志输出 ==========
log() {
    echo "[$(date '+%F %T')] $1" | tee -a "$LOGFILE"
}

# ========== 检查并创建日志目录 ==========
mkdir -p "$LOG_DIR"

# ========== 清理运行超时的进程 ==========
log "🔍 检查运行超时的 main_trader.py..."
ps -eo pid,etimes,cmd | grep "[m]ain_trader.py" | while read pid etime cmd; do
    if [ "$etime" -ge "$MAX_RUNTIME" ]; then
        log "⏱️ main_trader.py 已运行 $etime 秒，超过 $MAX_RUNTIME 秒，自动 kill PID=$pid"
        kill -9 "$pid"
    fi
done

# ========== 检查锁文件 ==========
if [ -e "$LOCKFILE" ]; then
    log "🚫 检测到锁文件，跳过本轮执行：$LOCKFILE"
    exit 1
fi

# ========== 创建锁文件 ==========
touch "$LOCKFILE"
log "🚀 开始执行 run_once.sh"

# ========== 激活虚拟环境 ==========
log "✅ 激活虚拟环境：$VENV_DIR"
source "$VENV_DIR/bin/activate"

# ========== 进入项目目录 ==========
cd "$PROJECT_DIR" || {
    log "❌ 无法进入项目目录 $PROJECT_DIR"
    rm -f "$LOCKFILE"
    exit 1
}

# ========== 拉取最新 Git 代码（可选） ==========
log "🔄 尝试拉取 Git 最新代码..."
git reset --hard HEAD
git clean -fd
git pull || {
    log "⚠️ Git 拉取失败，跳过执行"
    rm -f "$LOCKFILE"
    exit 1
}

# ========== 执行主程序 ==========
log "▶️ 执行 main_trader.py..."
python3 main_trader.py
RESULT=$?

# ========== 清理锁文件 ==========
rm -f "$LOCKFILE"
log "✅ 本轮执行完毕，退出码：$RESULT"
exit $RESULT