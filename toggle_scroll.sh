#!/bin/bash

export DISPLAY=:0
export XDG_RUNTIME_DIR=/run/user/$(id -u)

CONDA_PYTHON="/home/siriwuck_pop/miniconda3/envs/ar_pick/bin/python"
PROJECT_DIR="/home/siriwuck_pop/Public/backup_PJ/ar_pick/hand-tracking-using-mediapipe"
PROJECT_SCRIPT="$PROJECT_DIR/main.py"

cd "$PROJECT_DIR" || exit

# 🔍 ตรวจจับ PID ของ Python ตัวที่รันโปรเจกต์นี้อยู่จริงๆ
PID=$(pgrep -f "$PROJECT_SCRIPT")

if [ -z "$PID" ]; then
    # 🟢 เปิดโปรแกรม: สั่งรันด้วย sudo 
    sudo $CONDA_PYTHON $PROJECT_SCRIPT > /dev/null 2>&1 &
    notify-send "Air Scroll" "Activated 🟢 (Sudo Mode)"
else
    # 🔴 ปิดโปรแกรม: ใช้ sudo kill -9 เพื่อปลดล็อกกล้องเว็บแคมและดับ Process ทันที 100%
    sudo kill -9 $PID
    notify-send "Air Scroll" "Deactivated 🔴"
fi