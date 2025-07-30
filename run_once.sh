#!/bin/bash

# 设置锁文件路径，防止重复运行
LOCKFILE="/tmp/crypto_trader_lockfile"

# 如果锁存在，则退出
if [ -e "$LOCKFILE" ]; then
    echo "[WARN] 上一个进程尚未完成，跳过本轮执行。"
    exit 1
fi

# 创建锁文件
touch "$LOCKFILE"

# 启动日志记录
echo "[INFO] 开始执行 run_once.sh at $(date)"

# 激活虚拟环境
source /home/linuxuser/taenv/bin/activate

# 执行主交易脚本
python3 /home/linuxuser/crypto_trader_package/main_trader.py

# 删除锁文件
rm -f "$LOCKFILE"

# 结束日志记录