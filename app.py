
import re
import os
import sys
import json
import multiprocessing
import queue
import threading
import time
from src.fanqie_api import download, update
from flask import Flask, request, jsonify, make_response, abort, render_template, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime, timedelta
# 改用MySQL
import pymysql
from pymysql.cursors import Cursor as OriginalCursor
from loguru import logger
import logging
from timeout_decorator import TimeoutError

# 如果是docker环境，则检测是否挂载
if os.getenv("DOCKER_MODE") == "True":
    if not os.path.exists("/app/data/config.json"):
        print("Error: 请将配置文件挂载到 /app/data/config.json")
        sys.exit(1)
    if not os.path.exists("/app/data/output"):
        print("Error: 请将输出目录挂载到 /app/data/output")
        sys.exit(1)

    save_dir = "data/output"

    with open("data/config.json", "r", encoding='utf-8') as conf:
        try:
            config = json.load(conf)
        except json.JSONDecodeError as conf_e:
            raise json.JSONDecodeError("配置文件格式不正确", conf_e.doc, conf_e.pos)

    # docker模式忽略原配置
    config["save_dir"] = save_dir
    config["server"]["port"] = 5000
    config["server"]["host"] = "0.0.0.0"

else:
    with open("config.json", "r", encoding='utf-8') as conf:
        try:
            config = json.load(conf)
        except json.JSONDecodeError as conf_e:
            raise json.JSONDecodeError("配置文件格式不正确", conf_e.doc, conf_e.pos)
    save_dir = config["save_dir"]

os.makedirs(save_dir, exist_ok=True)

https = config["server"]["https"]["enable"]
cert_path = config["server"]["https"]["ssl_cert"]
key_path = config["server"]["https"]["ssl_key"]
try:
    start_hour = int(config["time_range"].split("-")[0])
    end_hour = int(config["time_range"].split("-")[1])
except ValueError:
    pass

if config["administrator"]["totp"]["enable"]:
    from pyotp import TOTP

    try:
        totp = TOTP(config["administrator"]["totp"]["secret"])
    except Exception:
        raise TypeError("管理员TOTP密钥格式不正确")

# 配置控制台和文件使用不同级别输出
logger.remove()
log_format = ("<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
              "<cyan>{extra[id]}</cyan> | <level>{message}</level>")
logger.add(config["log"]["filepath"], rotation=config["log"]["maxSize"], level=config["log"]["level"],
           retention=config["log"]["backupCount"], encoding="utf-8", enqueue=True, format=log_format)
logger.add(sys.stdout, level=config["log"]["console_level"], enqueue=True, format=log_format)
logger.configure(extra={"id": "None"})

app = Flask(__name__, template_folder='web', static_folder='web')
# 使用loguru的日志记录器替换flask的日志记录器

if config["cdn"] is False:
    class InterceptHandler(logging.Handler):
        def emit(self, record):
            excluded_module = 'qcloud_cos.cos_client:put_object'
            if excluded_module not in record.name:
                # Retrieve context where the logging call occurred, this happens to be in the 6th frame upward
                logger_opt = logger.opt(depth=6, exception=record.exc_info)
                logger_opt.log(record.levelno, record.getMessage())


    app.logger.addHandler(InterceptHandler())
    logging.basicConfig(handlers=[InterceptHandler()], level=20)


def get_ip():
    if config['cdn']:
        x_forwarded_for = request.headers.get('X-Forwarded-For')
        if x_forwarded_for:
            client_ip = x_forwarded_for.split(',')[0].strip()
            return client_ip
        else:
            return "Unknown IP"
    else:
        return get_remote_address()


if config["cors"]:
    from flask_cors import CORS
    CORS(app)
    logger.info("CORS跨域资源访问已启用")
else:
    logger.info("CORS跨域资源访问已禁用")
limiter = Limiter(
    key_func=get_ip,
    app=app,
    default_limits=["360 per day", "180 per hour"]
)
logger.info("程序初始化完成")


class AutoReconnectCursor(OriginalCursor):
    def execute(self, query, args=None):
        i = 1
        while i <= 3:
            try:
                return super().execute(query, args)
            except (pymysql.err.OperationalError, pymysql.err.InterfaceError):
                logger.warning(f"数据库连接中断，尝试重连（{i}/3）")
                self.connection.ping(reconnect=True)
                self.connection.select_db(config["mysql"]["database"])
            except Exception as e:
                logger.exception(e)
                logger.error(f"数据库操作失败: {e}，尝试重试（{i}/3）")
            i += 1
        logger.error("数据库操作失败，已达到最大重试次数")
        sys.exit(1)


# 创建并连接数据库
conn = pymysql.connect(
    host=config["mysql"]["host"],
    port=config["mysql"]["port"],
    user=config["mysql"]["user"],
    password=config["mysql"]["password"],
    charset='utf8mb4',
    autocommit=True,
    cursorclass=AutoReconnectCursor)
conn.cursor().execute("CREATE DATABASE IF NOT EXISTS %s" % config["mysql"]["database"])
conn.select_db(config["mysql"]["database"])

logger.info("数据库连接成功")

cursor = conn.cursor()

# 创建一个黑名单表
cursor.execute('''
CREATE TABLE IF NOT EXISTS blacklist
(
    ip           varchar(255) not null
        primary key,
    unblock_time text         null
);
''')

# 创建一个任务状态表
cursor.execute('''
CREATE TABLE IF NOT EXISTS novels
(
    num         int auto_increment,
    id          varchar(255) not null
        primary key,
    name        text         null,
    status      text         null,
    last_cid    text         null,
    last_update text         null,
    finished    int          null,
    constraint num
        unique (num)
);
''')

cursor.close()

logger.debug("数据库表创建成功或已存在")

logger.success("程序已启动")


@app.before_request
def block_method():
    logger.info(f"请求：{get_ip()} - {request.method} - {request.path}")
    if request.method == 'POST':
        ip = get_ip()
        conn.ping(reconnect=True)
        # 检查IP是否在黑名单中
        cur1 = conn.cursor()
        cur1.execute("SELECT unblock_time FROM blacklist WHERE ip=%s", (ip,))
        row = cur1.fetchone()
        if row is not None:
            # 检查限制是否已经解除
            unblock_time = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S.%f')
            if datetime.now() < unblock_time:
                response = make_response("Too many requests. You have been added to the blacklist for 1 hour.", 429)
                # 计算剩余的封禁时间（以秒为单位），并添加到'Retry-After'头部
                retry_after = int((unblock_time - datetime.now()).total_seconds())
                response.headers['Retry-After'] = str(retry_after)
                return response
            else:
                # 如果限制已经解除，那么从黑名单中移除这个IP
                cur1.execute("DELETE FROM blacklist WHERE ip=%s", (ip,))
        cur1.close()


@app.errorhandler(429)
def ratelimit_handler(_e):
    # 将触发限制的IP添加到黑名单中，限制解除时间为1小时后
    ip = get_ip()
    logger.warning(f"IP: {ip} 触发了限制，已被添加到黑名单")
    unblock_time = datetime.now() + timedelta(hours=1)
    cur0 = conn.cursor()
    cur0.execute("REPLACE INTO blacklist VALUES (%s, %s)", (ip, unblock_time.strftime('%Y-%m-%d %H:%M:%S.%f')))
    response = make_response("Too many requests. You have been added to the blacklist for 1 hour.", 429)
    response.headers['Retry-After'] = str(3600)  # 1小时的秒数
    cur0.close()
    return response


def book_id_to_url(book_id):
    return 'https://fanqienovel.com/page/' + book_id


def url_to_book_id(url):
    return re.search(r"page/(\d+)", url).group(1)


# 定义爬虫类
class Spider:
    def __init__(self):
        # 初始化URL队列
        self.url_queue = queue.Queue()
        # 设置运行状态为True
        self.is_running = True

    @staticmethod
    def crawl(url):
        book_id = url_to_book_id(url)
        try:
            logger.info(f"此书开始爬取", id=book_id)
            curm = conn.cursor()
            curm.execute("SELECT finished FROM novels WHERE id=%s", (book_id,))
            row = curm.fetchone()
            # 根据完结信息判断模式
            if row is not None and row[0] == 0:
                # 如果已有信息，使用增量更新模式
                logger.info(f"此书使用增量更新模式", id=book_id)
                curm.execute("SELECT name, last_cid FROM novels WHERE id=%s", (book_id,))
                row = curm.fetchone()
                title = row[0]
                last_cid = row[1]
                file_path = os.path.join(save_dir,
                                         config["filename_format"].format(title=title, book_id=book_id))
                logger.debug(f"名称: {title} 上次更新章节: {last_cid} 生成路径: {file_path} 开始更新", id=book_id)
                res = update(url, config["encoding"], last_cid, str(file_path), config)  # 提交任务
                # 获取任务和小说信息
                status, last_cid, finished = res
                logger.info("下载结束", id=book_id)
                # 写入数据库
                curm.execute("UPDATE novels SET last_cid=%s, last_update=%s, finished=%s WHERE id=%s",
                             (last_cid, datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'), finished, book_id))
                curm.close()
                if status == "completed":
                    return "completed"
                else:
                    return "failed"
            else:
                # 如果没有或者未成功，则普通下载
                logger.info(f"此书使用普通下载模式", id=book_id)
                logger.debug(f"此书开始下载", id=book_id)
                res = download(url, config["encoding"], config, save_dir)  # 提交任务
                # 获取任务和小说信息
                status, name, last_cid, finished = res
                logger.info("下载结束", id=book_id)
                # 写入数据库
                curm.execute("UPDATE novels SET name=%s, last_cid=%s, last_update=%s, finished=%s WHERE id=%s",
                             (name, last_cid, datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'), finished, book_id))
                curm.close()
                if status == "completed":
                    return "True"
                else:
                    return "False"
        except TimeoutError:
            logger.error(f"此书爬取超时", id=book_id)
            return "Timeout"
        except Exception as e:
            logger.error(f"此书爬取失败，错误信息: {e}", id=book_id)
            return "False"

    def worker(self):
        # 当运行状态为True时，持续工作
        while self.is_running:
            try:
                # 从URL队列中获取URL
                url = self.url_queue.get(timeout=1)
                book_id = url_to_book_id(url)
                curn = conn.cursor()
                logger.debug(f"此书开始任务", id=book_id)
                curn.execute("UPDATE novels SET status=%s WHERE id=%s", ("进行中", book_id))
                logger.debug(f"此书状态更新为进行中", id=book_id)
                status = Spider.crawl(url)
                # 调用爬虫函数爬取URL，如果出错则标记为失败并跳过这个任务进行下一个
                if status == "True":
                    curn.execute("UPDATE novels SET status=%s WHERE id=%s", ("已完成", book_id))
                    logger.debug(f"此书状态更新为已完成", id=book_id)
                elif status == "completed":
                    curn.execute("UPDATE novels SET status=%s WHERE id=%s", ("已更新完成", book_id))
                    logger.debug(f"此书状态更新为已更新完成", id=book_id)
                elif status == "failed":
                    curn.execute("UPDATE novels SET status=%s WHERE id=%s", ("更新失败", book_id))
                    logger.debug(f"此书状态更新为更新失败", id=book_id)
                elif status == "Timeout":
                    curn.execute("UPDATE novels SET status=%s WHERE id=%s", ("超时", book_id))
                    logger.debug(f"此书状态更新为超时", id=book_id)
                else:
                    curn.execute("UPDATE novels SET status=%s WHERE id=%s", ("失败", book_id))
                    logger.debug(f"此书状态更新为失败", id=book_id)
                curn.close()
                # 完成任务后，标记任务为完成状态
                self.url_queue.task_done()
                logger.debug(f"此书任务结束 结束状态: {status}", id=book_id)
            except queue.Empty:
                time.sleep(5)
                logger.trace("队列为空，等待5秒")
                continue

    def start(self):
        logger.info("爬虫工作启动")
        # 启动时检查数据库中是否有未完成的任务
        curc = conn.cursor()
        curc.execute("SELECT id FROM novels WHERE status IN (%s, %s, %s) ORDER BY num",
                     ("进行中", "等待中", "等待更新中"))
        rows = curc.fetchall()
        curc.close()
        if len(rows) == 0:
            logger.success("数据库中没有未完成的任务")
        if len(rows) > 0:
            logger.warning(f"数据库中有{len(rows)}个未完成的任务")
        # 有则添加到队列
        for row in rows:
            self.url_queue.put(book_id_to_url(row[0]))
            logger.debug(f"已添加到队列", id=row[0])
        # 启动工作线程
        threading.Thread(target=self.worker, daemon=True).start()

    def add_url(self, book_id):
        logger.debug(f"尝试添加此书到队列", id=book_id)
        cura = conn.cursor()
        cura.execute("SELECT status, finished FROM novels WHERE id=%s", (book_id,))
        row = cura.fetchone()
        if row is None or row[0] == "失败" or row[0] == "超时":
            self.url_queue.put(book_id_to_url(book_id))
            logger.debug(f"此书已添加到队列", id=book_id)
            cura.execute("REPLACE INTO novels (id, status) VALUES (%s, %s)", (book_id, "等待中"))
            cura.close()
            return "此书籍已添加到下载队列"
        else:
            # 如果已存在，检查书籍是否已完结
            if row[1] == 1:
                cura.close()
                logger.debug(f"此书已存在且已完结", id=book_id)
                # 如果已完结，返回提示信息
                return "此书籍已存在且已完结，请直接前往下载"
            elif row[0] == "等待中" or row[0] == "进行中" or row[0] == "等待更新中":
                cura.close()
                logger.debug(f"此书已存在且正在下载", id=book_id)
                # 如果正在下载，返回提示信息
                return "此书籍已存在且正在下载"
            else:
                cura.execute("SELECT last_update FROM novels WHERE id=%s", (book_id,))
                row = cura.fetchone()
                last_update = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S.%f')

                # 如果上次时间距现在小于3小时，返回提示
                if datetime.now() - last_update < timedelta(hours=3):
                    cura.close()
                    logger.debug(f"此书已存在且上次更新距现在不足3小时", id=book_id)
                    return "此书籍已存在且上次更新距现在不足3小时，请稍后再试"

                # 如果未完结，返回提示信息并尝试更新
                self.url_queue.put(book_id_to_url(book_id))
                cura.execute("UPDATE novels SET status=%s WHERE id=%s", ("等待更新中", book_id))
                cura.close()
                logger.debug(f"此书已添加到队列 (等待更新中)", id=book_id)
                return "此书籍已存在，正在尝试更新"

    def stop(self):
        logger.info("爬虫工作暂停")
        # 设置运行状态为False以停止工作线程
        self.is_running = False


# 创建爬虫实例并启动
spider = Spider()
spider.start()


def check_config(func):
    def wrapper(*args, **kwargs):
        if config["webui"]["enable"]:
            return func(*args, **kwargs)
        else:
            abort(404)
    return wrapper


@app.route('/', methods=['GET'], endpoint='index')
@app.route('/<path:filename>', methods=['GET'], endpoint='other')
@check_config
def index(filename='index.html'):
    if filename == 'index.html':
        return render_template('index.html', download_url=config["webui"]["download_url"])
    return app.send_static_file(filename)


@app.route('/api', methods=['POST'], endpoint='api')
@limiter.limit(f"{config['limiter']['api']['per_minute']}/minute;"
               f"{config['limiter']['api']['per_hour']}/hour;"
               f"{config['limiter']['api']['per_day']}/day")  # 限制请求
def api():

    # 判断是否在限时范围内
    now = datetime.utcnow() + timedelta(hours=8)
    if config["time_range"] == "false":
        pass
    else:
        if not (start_hour <= now.hour < end_hour):
            logger.debug(f"当前时间: {now.hour}点，不在时间范围内")
            return f"此服务只在{start_hour}点到{end_hour}点开放。", 503
        logger.debug(f"当前时间: {now.hour}点，请求通过")
    # 获取请求数据
    data = request.get_json()
    # 检查请求数据是否包含'action'和'id'字段，如果没有则返回400错误
    if 'action' not in data or 'id' not in data:
        logger.warning("请求缺少必要的json数据，返回400错误")
        return "Bad Request.The request is missing necessary json data.", 400
    if data['id'].isdigit():
        logger.debug(f"用户输入是纯数字，将被直接使用", id=data['id'])
        if len(data['id']) < 15:
            logger.info("用户输入的ID长度不正确，返回400错误")
            return "你输入的书籍ID长度不正确，仅支持番茄小说，请检查后再试。", 400
        pass
    else:
        if 'fanqienovel.com/page' in data['id']:
            logger.debug("用户输入了PC端目录页的链接，将被转换为ID")
            # noinspection PyBroadException
            try:
                data['id'] = re.search(r"page/(\d+)", data['id']).group(1)
            except Exception:
                logger.info("用户输入的链接转换失败，返回400错误")
                return "你输入的不是书籍ID或正确的链接。", 400
        elif 'changdunovel.com' in data['id']:
            logger.debug("用户输入了移动端分享链接，将被转换为ID")
            # noinspection PyBroadException
            try:
                data['id'] = re.search(r"book_id=(\d+)&", data['id']).group(1)
            except Exception:
                logger.info("用户输入的链接转换失败，返回400错误")
                return "你输入的不是书籍ID或正确的链接。", 400
        else:
            logger.info("用户的输入无法识别，返回400错误")
            return "你输入的不是书籍ID或正确的链接。", 400

    # 如果'action'字段的值为'add'，则尝试将URL添加到队列中，并返回相应的信息和位置
    if data['action'] == 'add':
        logger.info(f"请求: 添加: {data['id']}", id=data['id'])
        book_id = data['id']
        message = spider.add_url(book_id)
        url = book_id_to_url(book_id)
        position = list(spider.url_queue.queue).index(url) + 1 if url in list(spider.url_queue.queue) else None
        curq = conn.cursor()
        curq.execute("SELECT status, last_update FROM novels WHERE id=%s", (book_id,))
        row = curq.fetchone()
        curq.close()
        status = row[0] if row is not None else None
        if row is not None:
            last_update = row[1].split('.')[0] if row[1] is not None else None
        else:
            last_update = None
        logger.debug(f"返回信息: {message} 位置: {position} 状态: {status}", id=data['id'])
        return jsonify({'message': message, 'position': position, 'status': status, 'last_update': last_update})

    # 如果'action'字段的值为'query'，则检查URL是否在队列中，并返回相应的信息和位置或不存在的信息
    elif data['action'] == 'query':
        logger.debug(f"请求: 查询: {data['id']}", id=data['id'])
        book_id = data['id']
        url = book_id_to_url(book_id)
        position = list(spider.url_queue.queue).index(url) + 1 if url in list(spider.url_queue.queue) else None
        curw = conn.cursor()
        curw.execute("SELECT status, last_update FROM novels WHERE id=%s", (book_id,))
        row = curw.fetchone()
        curw.close()
        status = row[0] if row is not None else None
        if row is not None:
            last_update = row[1].split('.')[0] if row[1] is not None else None
        else:
            last_update = None
        logger.debug(f"返回信息: 状态: {status} 位置: {position}", id=data['id'])
        return jsonify({'exists': status is not None, 'position': position, 'status': status,
                        'last_update': last_update})

    else:
        return "Bad Request.The value of ‘action’ can only be ‘add’ or ‘query’.", 400


@app.route('/list', methods=['GET'], endpoint='list')
@limiter.limit(f"{config['limiter']['list']['per_minute']}/minute;"
               f"{config['limiter']['list']['per_hour']}/hour;"
               f"{config['limiter']['list']['per_day']}/day")  # 限制请求
def file_list():
    logger.debug("用户请求文件列表")
    folder_path = save_dir
    files = os.listdir(folder_path)
    # 按最后修改时间排序
    files.sort(key=lambda x: os.path.getmtime(os.path.join(folder_path, x)), reverse=True)
    file_links = ['<a href="/download/{}">{}</a>'.format(f, f) for f in files]
    return '<html><body>{}</body></html>'.format('<br>'.join(file_links))


@app.route('/download/<path:filename>', methods=['GET'], endpoint='download')
@limiter.limit(f"{config['limiter']['download']['per_minute']}/minute;"
               f"{config['limiter']['download']['per_hour']}/hour;"
               f"{config['limiter']['download']['per_day']}/day")  # 限制请求
def download_file(filename):
    logger.debug(f"用户请求下载文件: {filename}")
    directory = os.path.abspath(save_dir)
    try:
        logger.debug(f"尝试返回文件: {filename}")
        return send_from_directory(directory, filename, as_attachment=True)
    except FileNotFoundError:
        logger.warning(f"文件: {filename} 不存在，返回404错误")
        return "File not found.", 404


@logger.catch
@app.route('/manage/<group>/<action>', methods=['GET', 'POST'], endpoint='manage')
def manage(group, action):
    global config
    logger.info(f"管理员请求管理接口，组: {group} 动作: {action}")
    if config["administrator"]["enable"] is False:
        logger.warning("管理员功能已被禁用，返回403错误")
        return "此功能已被禁用", 403
    if group == "check":
        if action == "passwd":
            try:
                passwd = request.args["passwd"]
            except KeyError:
                return "请求未携带密码，无权限访问"
            if passwd != config["administrator"]["password"]:
                return "密码错误，无权限访问"
            return "密码正确"
        elif action == "alive":
            return "alive"
        elif action == "totp":
            if config["administrator"]["totp"]["enable"]:
                try:
                    totp_code = request.args["totp"]
                except KeyError:
                    return "请求未携带TOTP验证码"
                if not totp.verify(totp_code):
                    return "TOTP验证码错误"
                return "TOTP验证码正确"
            else:
                return "此功能未开启"
        else:
            return "Bad Request.", 400
    try:
        passwd = request.args["passwd"]
    except KeyError:
        return "请求未携带密码，无权限访问", 403
    if passwd != config["administrator"]["password"]:
        return "密码错误，无权限访问", 403
    if config["administrator"]["totp"]["enable"]:
        try:
            totp_code = request.args["totp"]
        except KeyError:
            return "请求未携带TOTP验证码，无权限访问", 403
        if not totp.verify(totp_code):
            return "TOTP验证码错误，无权限访问", 403
    logger.success("管理员身份验证通过")

    if group == "main":
        if action == "pause":
            spider.stop()
            return "已暂停"
        elif action == "start":
            spider.start()
            return "已启动"
        elif action == "status":
            return "正在运行" if spider.is_running else "已暂停"
        elif action == "update-config":
            with open("data/config.json", "r", encoding='utf-8') as conf_u:
                try:
                    config = json.load(conf_u)
                except json.JSONDecodeError:
                    return "配置文件格式不正确"
            return "已重新加载配置文件，部分配置需要重启服务器才能生效"
        else:
            return "Bad Request.", 400

    elif group == "tasks":
        curt = conn.cursor()
        if action == "list-new":
            tasks_dict = {}
            curt.execute("SELECT id, status FROM novels ORDER BY num DESC LIMIT 30", ())
            for i, row in enumerate(curt.fetchall()):
                tasks_dict[f'task{i}'] = {'id': row[0], 'status': row[1]}
            curt.close()
            return jsonify(tasks_dict)
        elif action == "list-all":
            if config["administrator"]["enable-list-all-tasks"] is False:
                return "此功能已被禁用", 403
            tasks_dict = {}
            curt.execute("SELECT id, status FROM novels")
            for i, row in enumerate(curt.fetchall()):
                tasks_dict[f'task{i}'] = {'id': row[0], 'status': row[1]}
            curt.close()
            return jsonify(tasks_dict)
        elif action == "list-tasks-all":
            # 已废弃的动作
            curt.close()
            return "请直接使用数据库管理工具查看", 410
        elif action == "clear":
            while not spider.url_queue.empty():
                try:
                    spider.url_queue.get_nowait()
                except queue.Empty:
                    break
            curt.close()
            return "已清空"
        else:
            curt.close()
            return "Bad Request.", 400

    elif group == "blacklist":
        curb = conn.cursor()
        if action == "list":
            curb.execute("SELECT * FROM blacklist")
            rows = curb.fetchall()
            curb.close()
            return jsonify(rows)
        elif action == "add":
            ip = request.args["ip"]
            if "time" not in request.args:
                unblock_time = datetime.now() + timedelta(hours=1)
                curb.execute("REPLACE INTO blacklist VALUES (%s, %s)",
                             (ip, unblock_time.strftime('%Y-%m-%d %H:%M:%S.%f')))
                curb.close()
                return "已添加，解除时间为1小时后"
            else:
                try:
                    unblock_time = datetime.now() + timedelta(hours=int(request.args["time"]))
                    curb.execute("REPLACE INTO blacklist VALUES (%s, %s)",
                                 (ip, unblock_time.strftime('%Y-%m-%d %H:%M:%S.%f')))
                    curb.close()
                    return f"已添加，解除时间为{request.args['time']}小时后"
                except ValueError:
                    curb.close()
                    return "时间格式不正确"
        elif action == "remove":
            ip = request.args["ip"]
            curb.execute("DELETE FROM blacklist WHERE ip=%s", (ip,))
            curb.close()
            return f"已移除 {ip}"
        elif action == "clear":
            # noinspection SqlWithoutWhere
            curb.execute("DELETE FROM blacklist")
            curb.close()
            return "已清空黑名单"
        else:
            curb.close()
            return "Bad Request.", 400

    else:
        return "Bad Request.", 400


# @app.route('/<path:filename>')
# @check_config
# def static_file(filename):
#     return send_from_directory('web', filename)


if __name__ == "__main__":
    # 如果你使用WSGI服务器，你可以将下面的内容放到你的WSGI服务器配置文件中
    multiprocessing.freeze_support()

    if https:
        print("HTTPS is enabled.")
        # 如果启用了HTTPS
        app.run(host=config["server"]["host"],
                port=config["server"]["port"],
                threaded=config["server"]["thread"],
                debug=config["server"]["debug"],
                ssl_context=(cert_path, key_path)
                )
    else:
        print("HTTPS is disabled.")
        # 如果没有启用HTTPS
        app.run(host=config["server"]["host"],
                port=config["server"]["port"],
                threaded=config["server"]["thread"],
                debug=config["server"]["debug"]
                )
