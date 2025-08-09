#!/bin/bash
set -euo pipefail

# ========== 可配 ==========
PROJECT_DIR="/home/linuxuser/crypto_trader_package"
VENV_DIR="/home/linuxuser/taenv"
LOG_DIR="/home/linuxuser/trade_logs"
LOCKFILE="/tmp/crypto_trader_lockfile"
MAX_RUNTIME=600                       # main_trader.py 最大允许运行秒数
TARGET_BRANCH="${1:-big}"             # 默认跑 big 分支；可传参覆盖
LOGFILE="$LOG_DIR/cron_runonce_$(date '+%Y%m%d').log"
ENV_FILE="$PROJECT_DIR/.env"
ENV_BAK="/tmp/crypto_trader_env.$(date +%s).bak"

# ========== 日志 ==========
log(){ echo "[$(date '+%F %T')] $*" | tee -a "$LOGFILE"; }

# ========== 保障 ==========
mkdir -p "$LOG_DIR"

cleanup(){
  # 解锁并清理锁文件
  { flock -u 9 2>/dev/null || true; } && rm -f "$LOCKFILE" 2>/dev/null || true
}
trap cleanup EXIT

# ========== 单实例锁（非阻塞）==========
exec 9> "$LOCKFILE" || true
if ! flock -n 9; then
  log "🚫 检测到锁文件（已有实例在运行），退出：$LOCKFILE"
  exit 0
fi

# ========== 超时进程清理 ==========
log "🔍 检查运行超时的 main_trader.py..."
pgrep -af main_trader.py || log "ℹ️ 当前无运行中的 main_trader.py 进程"
# 杀掉超过 MAX_RUNTIME 的 main_trader.py（尽量温和）
while read -r pid etime cmd; do
  if [[ -n "${pid:-}" && -n "${etime:-}" && "$etime" -ge "$MAX_RUNTIME" ]]; then
    log "⏱️ main_trader.py 已运行 ${etime}s，超过 ${MAX_RUNTIME}s，kill -9 PID=$pid"
    kill -9 "$pid" || true
  fi
done < <(ps -eo pid,etimes,cmd | grep "[m]ain_trader.py")

# ========== 启动 ==========
log "🚀 开始执行 run_once.sh"

# 虚拟环境
if [[ -f "$VENV_DIR/bin/activate" ]]; then
  log "✅ 激活虚拟环境：$VENV_DIR"
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
else
  log "⚠️ 未找到虚拟环境 $VENV_DIR，继续使用系统 Python"
fi

# 进入项目
cd "$PROJECT_DIR" || { log "❌ 无法进入项目目录 $PROJECT_DIR"; exit 1; }

# 在 git 操作前备份 .env（若存在）
if [[ -f "$ENV_FILE" ]]; then
  cp -f "$ENV_FILE" "$ENV_BAK"
  log "🧰 已备份 .env 到 $ENV_BAK"
fi

# 同步代码（忽略 .env）
log "🔄 切换并拉取 Git 分支：$TARGET_BRANCH ..."
git fetch origin || log "⚠️ git fetch 警告，继续"
git checkout "$TARGET_BRANCH" || { log "❌ 切换分支失败"; exit 1; }
git reset --hard "origin/$TARGET_BRANCH" || log "⚠️ git reset 警告"
git clean -fd -e .env || log "⚠️ git clean 警告（已忽略 .env）"
git pull origin "$TARGET_BRANCH" || log "⚠️ git pull 警告"

# 如 .env 被删，尝试还原备份
if [[ ! -f "$ENV_FILE" && -f "$ENV_BAK" ]]; then
  cp -f "$ENV_BAK" "$ENV_FILE"
  log "♻️ 已从备份还原 .env"
fi

# 加载 .env（不回显内容）
if [[ -f "$ENV_FILE" ]]; then
  set -a; # 将 source 的变量导出为环境变量
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  log "🔑 已加载 .env 环境变量"
else
  # 兜底：从家目录的私有副本加载
  if [[ -f "$HOME/.env.crypto" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$HOME/.env.crypto"
    set +a
    log "🔑 已从 $HOME/.env.crypto 加载环境变量（兜底）"
  else
    log "⚠️ 未找到 .env 或 $HOME/.env.crypto，依赖系统环境变量继续"
  fi
fi

# 运行
log "▶️ 执行 main_trader.py..."
python3 main_trader.py || true
RESULT=$?

# 结束
log "✅ 本轮执行完毕，退出码：$RESULT"
exit "$RESULT"