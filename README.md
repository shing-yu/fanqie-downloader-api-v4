# 番茄下载器API V4版本

基于先前版本 [novel-downloader-api](https://github.com/shing-yu/novel-downloader-api) （已存档）番茄部分升级的API

# 部署教程

## Docker部署（推荐）

p.s. 如果镜像拉取缓慢，可参考 [配置镜像加速器_容器镜像服务(ACR)-阿里云帮助中心 (aliyun.com)](https://help.aliyun.com/zh/acr/user-guide/accelerate-the-pulls-of-docker-official-images) 进行加速

### 无MySQL

如果你没有MySQL服务，或想新建一个，可以使用带有`版本号-mysql`或`latest`标签的docker镜像，镜像内自带MySQL

部署命令：

```shell
sudo docker run -d \
  -e MYSQL_ROOT_PASSWORD=123456 \
  -v /opt/fdapiv4/mysql:/var/lib/mysql \
  -v /opt/fdapiv4/config.json:/app/data/config.json \
  -v /opt/fdapiv4/output:/app/data/output \
  -v /opt/fdapiv4/logs:/app/logs \
  -p 5000:5000 \
  -p 3306:3306 \
  --name fdapiv4 \
  --restart unless-stopped \
  shingyu/fanqie-downloader-api-v4:latest-mysql
```

[# 参数说明](#参数说明)

环境变量`MYSQL_ROOT_PASSWORD`的值将被设置为MySQL的root用户密码，可根据需要自行更改

该密码需要手动填入配置文件`mysql.password`中

挂载的源目录和配置文件路径及容器名称可根据需要与实际情况自行更改

配置文件内容说明请看 [# 配置文件说明](#配置文件说明)

<br>

### 已有MySQL

如果你已有部署完成的MySQL服务，可以使用带有`版本号-nomysql`标签的镜像

部署命令：

```shell
sudo docker run -d \
  -v /opt/fdapiv4/config.json:/app/data/config.json \
  -v /opt/fdapiv4/output:/app/data/output \
  -v /opt/fdapiv4/logs:/app/logs \
  -p 5000:5000 \
  --name fdapiv4 \
  --restart unless-stopped \
  shingyu/fanqie-downloader-api-v4:latest-nomysql
```

[# 参数说明](#参数说明)

**对于已有的MySQL服务的信息，需要在配置文件内`mysql`字段中填入相关信息**

**（如果服务在本地，请注意docker访问主机的相关配置！）**

挂载的源目录和配置文件路径及容器名称可根据需要与实际情况自行更改

配置文件内容说明请看 [# 配置文件说明](#配置文件说明)

<br>

### 容器管理命令

- 启动

```shell
sudo docker start fdapiv4
```

- 停止

```shell
sudo docker stop fdapiv4
```

- 重启

```shell
sudo docker restart fdapiv4
```

<br>

### 参数说明

| 参数                                              | 说明                          |
| ------------------------------------------------- | ----------------------------- |
| -d                                                | 后台运行                      |
| -e MYSQL_ROOT_PASSWORD=123456                     | 设置MySQL初始密码，可自行修改 |
| -v /opt/fdapiv4/mysql:/var/lib/mysql              | 挂载MySQL数据库信息           |
| -v /opt/fdapiv4/config.json:/app/data/config.json | 挂载程序配置文件              |
| -v /opt/fdapiv4/output:/app/data/output           | 挂载程序输出目录              |
| -v /opt/fdapiv4/logs:/app/logs                    | 挂载程序日志目录              |
| -p 5000:5000                                      | 暴露程序端口                  |
| -p 3306:3306                                      | 暴露MySQL端口                 |
| --name fdapiv4                                    | 容器名称，可自行修改          |
| --restart unless-stopped                          | 随系统启动，非主动退出时重启  |
| shingyu/fanqie-downloader-api-v4                  | 从docker hub拉取镜像          |

挂载参数和端口参数可根据需求与实际情况自行调整

<br>

## 直接部署

### 环境要求

- Python 3.x （作者：3.11.5）
- pip包管理工具
- MySQL 5.x/8.x（不一定本地，作者：8.0.36）

### 一、获取源代码

**使用Git Clone获取**

```bash 
git clone https://github.com/shing-yu/fanqie-downloader-api-v4.git
cd fanqie-downloader-api-v4
```

或者：

**下载压缩包**

① 访问项目 GitHub 页面: [fanqie-downloader-api-v4](https://github.com/shing-yu/fanqie-downloader-api-v4)  
② 点击 "Clone or download" 按钮  
③ 选择 "Download ZIP"  
④ 解压下载的压缩包至你想要保存项目的目录  
⑤ 在目录中打开终端

<br>

### 二、创建虚拟环境（可选）

**创建虚拟环境**

```bash
python -m venv venv
# python3 -m venv venv
```

**激活虚拟环境**

- Windows:

```bash
venv\Scripts\activate
```

- MacOS/Linux:

```bash
source venv/bin/activate
```

<br>

### 三、安装依赖并运行

**使用pip安装依赖**

```bash
pip install -r requirements.txt
# pip3 install -r requirements.txt
```

**按需修改配置文件**

请参考 [# 配置文件说明](#配置文件说明)

<br>

**运行项目：**

```bash
python app.py
# python3 app.py
```

<br>

## 配置文件说明

使用方式：复制/下载[config-example.json](https://github.com/shing-yu/fanqie-downloader-api-v4/blob/main/config-example.json)文件，并重命名为config.json，然后修改为你自己的配置

| 属性              | 说明                                                                                   | 默认值         |
|-------------------|----------------------------------------------------------------------------------------|----------------|
| wsgi              | 是否使用了WSGI服务器（不同行为）                                             | false          |
| cors                                | 是否允许跨域资源访问                    | false          |
| cdn               | 是否使用了CDN（不同行为）                                                                  | false          |
| webui.enable      | 是否启用Web用户界面                                                                     | true           |
| webui.download_url | 你的下载地址，用于引导用户前往下载 | https://example.com/ |
| log.level         | 日志文件记录级别                                                                           | DEBUG          |
| log.console_level | 控制台日志输出级别                                                                     | INFO           |
| log.filepath      | 日志文件路径                                                                           | logs/api.log   |
| log.maxSize       | 日志文件最大大小                                                                       | 20 MB          |
| log.backupCount   | 日志文件备份数量                                                                       | 20             |
| server.port       | 服务器端口（docker部署无效）                                                              | 5000           |
| server.host       | 监听地址（docker部署无效）                                                                   | 0.0.0.0        |
| server.debug      | 是否启用调试模式                                                                       | false          |
| server.thread     | 是否启用多线程模式                                                                     | false          |
| server.https.enable| 是否启用HTTPS                                                             | false          |
| server.https.ssl_cert| HTTPS SSL证书路径（启用需配置）                                                             | ""             |
| server.https.ssl_key | HTTPS SSL密钥路径（启用需配置）                                                            | ""             |
| server.https.force_https| 是否强制使用HTTPS                                                          | false          |
| mysql.host        | MySQL主机地址                                                                     | 127.0.0.1             |
| mysql.port        | MySQL端口号                                                                            | 3306           |
| mysql.user        | MySQL用户名                                                                            | root           |
| mysql.password    | MySQL密码                                                                              | _空_          |
| mysql.database    | MySQL数据库名称                                                                        | fanqieapi      |
| administrator.enable| 是否启用管理员接口                                                                    | false          |
| administrator.password| 管理员密码（启用需配置）                                                                  | L147258963oOOi|
| administrator.totp.enable| 是否对管理行为二次验证                                           | false          |
| administrator.totp.secret| 双因素认证密钥（启用需配置）                                                             | _空_                  |
| administrator.enable_list_all_tasks| 是否允许列出所有任务                                                               | false          |
| save_dir          | 下载保存目录（docker部署无效）                                                           | output         |
| encoding          | 编码方式                                                                               | utf-8          |
| filename_format   | 文件名格式                                                                             | {title}_{book_id}.txt |
| speed_limit       | 下载速度限制（最低0.25，单位秒）                                                        | 0.5            |
| time_range        | 可用时间范围限制（如”8-18“）                                                                | false          |
| limiter.enable    | 是否启用限速器                                                                         | true           |
| limiter.\*.per_minute | 每分钟请求限制数量                                                               |                       |
| limiter.\*.per_hour | 每小时请求限制数量                                                                 |             |
| limiter.\*.per_day | 每日请求限制数量                       |             |
| upload.base_dir   | 上传基础目录                                                                           | API/小说       |
| upload.cos.enable | 是否启用腾讯云对象存储                                                                 | false          |
| upload.cos.secret_id| 腾讯云对象存储SecretId（启用需配置）                                                       | ""             |
| upload.cos.secret_key| 腾讯云对象存储SecretKey（启用需配置）                                                      | ""             |
| upload.cos.region  | 腾讯云对象存储地区（启用需配置）                                                              | ap-xxxxxxxx   |
| upload.cos.bucket  | 腾讯云对象存储Bucket名称（启用需配置）                                                       | xxx-0000000000|
| upload.cos.scheme  | 腾讯云对象存储访问协议                                                                 | https          |
| upload.cos.token   | 腾讯云对象存储Token                                                                    | null           |
| upload.ofb.enable | 是否启用OneDrive for Business（未实现）                                                    | false          |
| upload.ofb.client_id| OFB客户端ID（启用需配置）（未实现）                                            | your_client_id |
| upload.ofb.client_secret| OFB客户端密钥（启用需配置）（未实现）                                         | your_client_secret |
| upload.ofb.tenant_id| OFB租户ID（启用需配置）（未实现）                                              | your_tenant_id |
| upload.ofb.endpoint | 上传端点路径（未实现）                      | /Documents/    |

对于 `mysql.host` ，如果使用docker部署，请考虑使用IP地址代替主机名，否则可能由于DNS问题导致访问速度极慢报错。

<br>

默认配置文件：

```json
{
  "wsgi": false,
  "cors": false,
  "cdn": false,
  "webui": {
    "enable": true,
    "download_url": "https://example.com/"
  },
  "log": {
    "level": "DEBUG",
    "console_level": "INFO",
    "filepath": "logs/api.log",
    "maxSize": "20 MB",
    "backupCount": 20
  },
  "server": {
    "port": 5000,
    "host": "0.0.0.0",
    "debug": false,
    "thread": false,
    "https": {
      "enable": false,
      "ssl_cert": "",
      "ssl_key": "",
      "force_https": false
    }
  },
  "mysql": {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "",
    "database": "fanqieapi"
  },
  "administrator": {
    "enable": false,
    "password": "L147258963oOOi",
    "totp": {
      "enable": false,
      "secret": ""
    },
    "enable_list_all_tasks": false
  },
  "save_dir": "output",
  "encoding": "utf-8",
  "filename_format": "{title}_{book_id}.txt",
  "speed_limit": 0.5,
  "time_range": "false",
  "limiter": {
    "enable": true,
    "api": {
      "per_minute": "15",
      "per_hour": "200",
      "per_day": "300"
    },
    "list": {
      "per_minute": "20",
      "per_hour": "200",
      "per_day": "500"
    },
    "download": {
      "per_minute": "10",
      "per_hour": "100",
      "per_day": "300"
    }
  },
  "upload": {
    "base_dir": "API/小说",
    "cos": {
      "enable": false,
      "secret_id": "",
      "secret_key": "",
      "region": "ap-xxxxxxxx",
      "bucket": "xxx-0000000000",
      "scheme": "https",
      "token": null
    },
    "ofb":{
      "comment": "OneDrive for Business",
      "enable": false,
      "client_id": "your_client_id",
      "client_secret": "your_client_secret",
      "tenant_id": "your_tenant_id",
      "endpoint": "/Documents/"
    }
  }

}
```
