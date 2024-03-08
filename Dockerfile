# 使用官方Mysql镜像
FROM mysql:8.0-debian

WORKDIR /app

# APT换源
#RUN rm -rf /etc/apt/sources.list.d/*
#RUN echo "deb http://mirrors.aliyun.com/debian/ buster main contrib non-free" > /etc/apt/sources.list \
#    && echo "deb http://mirrors.aliyun.com/debian/ buster-updates main contrib non-free" >> /etc/apt/sources.list \
#    && echo "deb http://mirrors.aliyun.com/debian/ buster-backports main contrib non-free" >> /etc/apt/sources.list \
#    && echo "deb http://mirrors.aliyun.com/debian-security buster/updates main contrib non-free" >> /etc/apt/sources.list

# 安装证书
RUN apt-get update && apt-get install -y ca-certificates

# 安装Python
RUN apt-get install -y python3 python3-pip
#RUN python3 -m pip install --upgrade pip
#RUN python3 -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制文件
COPY . /app

RUN chmod +x /app/entrypoint.sh
RUN chmod +x /app/start.sh

# 安装依赖
RUN pip3 install --no-cache-dir -r /app/requirements.txt
#RUN pip3 install --no-cache-dir -r /app/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 配置MySQL
RUN echo "skip-name-resolve" >> /etc/mysql/my.cnf
RUN echo "general_log = 1" >> /etc/mysql/my.cnf
RUN echo "general_log_file = /var/lib/mysql/general.log" >> /etc/mysql/my.cnf

EXPOSE 5000
EXPOSE 3306

ENV DOCKER_MODE=True

# 声明挂载Mysql数据库
VOLUME /var/lib/mysql

ENTRYPOINT ["/app/start.sh"]