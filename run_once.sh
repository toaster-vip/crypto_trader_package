#!/bin/bash
set -euo pipefail

# ====== 可配项 ======
PROJECT_DIR="/home/linuxuser/crypto_trader_package"
VENV_DIR="/home/linuxuser/taenv"
LOG_DIR="/home/linuxuser/trade_logs"
LOCKFILE="/tmp/crypto_trader_lockfile"          # flock 锁文件
MAX_RUNTIME=600                                  # main_trader.py 最大允许运行秒数
TARGET_BRANCH="${1:-big}"                        # 默认分支 big
LOGFILE="$LOG_DIR/cron_runonce_$(date '+%Y%m%d').log"
ENV_FILE="$PROJECT_DIR/.env"
ENV_BAK="/tmp/crypto_trader_env.$(date +%s).bak"

# ====== 日志函数 ======
log(){ echo "[$(date '+%F %T')] $*" | tee -a "$LOGFILE"; }

# ====== 目录准备 ======
mkdir -p "$LOG_DIR"

# ====== 获取锁，防并发 ======
exec {LOCKFD}>"$LOCKFILE"
if ! flock -n ${LOCKFD}; then
  log "🚫 已有实例在运行，跳过本轮：$LOCKFILE"
  exit 1
fi
cleanup() {
  flock -u ${LOCKFD} || true
  rm -f "$LOCKFILE" || true
}
trap cleanup EXIT

log "🔍 检查运行超时的 main_trader.py..."

# —— 安全检查：无匹配不失败 ——
if pgrep -af main_trader.py >/dev/null 2>&1; then
  # 逐个检查运行时长
  ps -eo pid,etimes,cmd | awk '/main_trader\.py/ && !/awk/ {print $1, $2}' | while read -r pid etime; do
    if [ "${etime:-0}" -ge "$MAX_RUNTIME" ]; then
      log "⏱️ main_trader.py 已运行 $etime 秒，超过 $MAX_RUNTIME 秒，kill PID=$pid"
      kill -9 "$pid" || true
    fi
  done
else
  log "ℹ️ 当前无运行中的 main_trader.py 进程"
fi

log "🚀 开始执行 run_once.sh"

# ====== 激活虚拟环境 ======
if [ -f "$VENV_DIR/bin/activate" ]; then
  log "✅ 激活虚拟环境：$VENV_DIR"
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
else
  log "⚠️ 未找到虚拟环境 $VENV_DIR，使用系统 Python"
fi

# ====== 进入项目目录 ======
cd "$PROJECT_DIR" || { log "❌ 无法进入项目目录 $PROJECT_DIR"; exit 1; }

# ====== git 前备份 .env ======
if [ -f "$ENV_FILE" ]; then
  cp -f "$ENV_FILE" "$ENV_BAK"
  log "🧰 已备份 .env 到 $ENV_BAK"
fi

# ====== 拉取指定分支最新代码 ======
log "🔄 切换并拉取 Git 分支：$TARGET_BRANCH ..."
git fetch origin || log "⚠️ git fetch 警告，继续"
git checkout "$TARGET_BRANCH" || { log "❌ 切分支失败"; exit 1; }
git reset --hard "origin/$TARGET_BRANCH" || log "⚠️ git reset 警告"
git clean -fd || log "⚠️ git clean 警告"
git pull origin "$TARGET_BRANCH" || log "⚠️ git pull 警告"

# ====== 如 .env 被删，自动还原 ======
if [ ! -f "$ENV_FILE" ] && [ -f "$ENV_BAK" ]; then
  cp -f "$ENV_BAK" "$ENV_FILE"
  log "♻️ 已还原 .env"
fi

# ====== 加载 .env（安全方式，不打印变量）======
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  log "🔑 已加载 .env 环境变量"
else
  log "⚠️ 未找到 .env，依赖系统环境变量继续"
fi

# ====== 执行主程序 ======
log "▶️ 执行 main_trader.py..."
python3 main_trader.py || true
RESULT=$?

log "✅ 本轮执行完毕，退出码：$RESULT"
exit "$RESULT"