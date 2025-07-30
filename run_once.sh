#!/bin/bash

# 设置路径
PROJECT_DIR="/home/linuxuser/crypto_trader_package"
VENV_DIR="/home/linuxuser/taenv"
LOCKFILE="/tmp/crypto_trader_lockfile"

# 如果锁文件存在，则退出
if [ -e "$LOCKFILE" ]; then
    echo "[WARN] 上一个进程尚未完成，跳过本轮执行。"
    exit 1
fi

# 创建锁文件
touch "$LOCKFILE"

# 启动日志记录
echo "[INFO] 🚀 开始执行 run_once.sh at $(date)"

# 激活虚拟环境
echo "[INFO] ✅ 激活虚拟环境：$VENV_DIR"
source "$VENV_DIR/bin/activate"

# 进入项目目录
cd "$PROJECT_DIR" || {
    echo "[ERROR] ❌ 无法进入项目目录 $PROJECT_DIR"
    rm -f "$LOCKFILE"
    exit 1
}

# 拉取最新代码
echo "[INFO] 🔄 拉取 Git 最新代码..."
git pull

# 执行主交易脚本
echo "[INFO] ▶️ 执行 main_trader.py..."
python3 main_trader.py

# 删除锁文件
rm -f "$LOCKFILE"
echo "[INFO] ✅ 本轮执行完毕 at $(date)"