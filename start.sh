#!/bin/bash

# 检测环境变量
if [ -z "$MYSQL_ROOT_PASSWORD" ] && [ -z "$MYSQL_ALLOW_EMPTY_PASSWORD" ] && [ -z "$MYSQL_RANDOM_ROOT_PASSWORD" ]; then
    echo "start.sh------Environment variables are not set correctly."
    echo "Please specify one of the following environment variables:"
    echo "- MYSQL_ROOT_PASSWORD"
    echo "- MYSQL_ALLOW_EMPTY_PASSWORD"
    echo "- MYSQL_RANDOM_ROOT_PASSWORD"
    exit 1
else
    echo "start.sh------Environment variables are set correctly."
fi

# 使用MySQL官方启动脚本启动数据库
/app/entrypoint.sh mysqld &

# 设置计数器的次数上限
max_attempts=30
attempt_count=0

# 当 MySQL 未启动时执行循环
while ! mysqladmin ping -h"localhost" --silent; do
    # 检查是否超过了次数上限
    if [ $attempt_count -eq $max_attempts ]; then
        echo "start.sh------Reached maximum attempts. MySQL did not start."
        exit 1
    fi
    
    # 增加尝试次数计数器
    ((attempt_count++))
    
    echo "start.sh------Waiting for MySQL to start... Attempt $attempt_count"
    sleep 1
done

# 如果 MySQL 启动成功，则输出成功信息
echo "start.sh------MySQL started successfully!"

echo "start.sh------Waiting for MySQL to be ready..."
sleep 15

# 使用gunicorn启动Flask应用
/app/venv/bin/gunicorn -w 1 -b 0.0.0.0:5000 app:app