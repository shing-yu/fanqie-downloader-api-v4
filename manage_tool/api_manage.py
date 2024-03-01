import requests
import json
import urllib.parse
import os
from sys import exit
import pyotp


def check_alive():
    # GET请求
    response2 = requests.get(api_url.format(group="check", action="alive"))
    if response2.text == "alive":
        return True
    else:
        return False


# 验证密码是否正确
def verify_password(passwd):
    # GET请求
    response1 = requests.get(api_url.format(group="check", action="passwd"), params={"passwd": passwd})
    return response1.text


def verify_totp(totp_now_):
    # GET请求
    response3 = requests.get(api_url.format(group="check", action="totp"), params={"totp": totp_now_})
    return response3.text


# 通过可选传入参数和密码以及TOTP密钥构建字典
def get_params(**kwargs):
    params = {"passwd": password}
    if secret != "":
        params["totp"] = totp.now()
    params.update(kwargs)
    return params


def clear_screen():
    # 根据系统判断指令
    if os.name == "nt":
        os.system("cls")
    else:
        os.system("clear")


print("API管理工具")
api_url = input("请输入API地址：（如：http://localhost:5000/api）\n")

# 提取基础url，使用urlparse模块
api_url = urllib.parse.urlparse(api_url).scheme + "://" + urllib.parse.urlparse(api_url).netloc
api_url = api_url + "/manage/{group}/{action}"

print("正在检查API地址是否有效...")
if not check_alive():
    print("API地址无效，请检查后重试。")
    input()
    exit(1)

while True:
    password = input("请输入密码：")
    print("正在验证密码...")
    verify_result = verify_password(password)
    print(verify_result)
    if verify_result == "密码正确":
        break
    else:
        print("密码错误，请重试。")
        clear_screen()

while True:
    secret = input("请输入你的TOTP密钥：（未启用请直接回车）\n")
    if secret == "":
        break
    # noinspection PyBroadException
    try:
        totp = pyotp.TOTP(secret)
        print("正在验证TOTP密钥...")
        totp_now = totp.now()
        verify_result = verify_totp(totp_now)
        print(verify_result)
        if verify_result == "TOTP验证码正确":
            break
        else:
            clear_screen()
    except Exception:
        print("密钥格式错误，请重试。")


while True:
    clear_screen()
    print("请选择你要管理的操作类别：")
    print("1. 主程序")
    print("2. 任务列表")
    print("3. 黑名单")
    input_num = input("请输入序号：")
    if input_num == "1":
        while True:
            group = "main"
            clear_screen()
            print("请选择你要管理的操作：")
            print("1. 暂停主程序")
            print("2. 启动主程序")
            print("3. 查看主程序状态")
            print("4. 更新配置文件")
            print("5. 返回上一级")
            input_num = input("请输入序号：")
            if input_num == "1":
                print("正在暂停主程序...")
                response = requests.post(api_url.format(group=group, action="pause"), params=get_params())
                print(response.text)
                input("按回车键继续...")
            elif input_num == "2":
                print("正在启动主程序...")
                response = requests.post(api_url.format(group=group, action="start"), params=get_params())
                print(response.text)
                input("按回车键继续...")
            elif input_num == "3":
                print("正在获取主程序状态...")
                # GET请求
                response = requests.get(api_url.format(group=group, action="status"), params=get_params())
                print(response.text)
                input("按回车键继续...")
            elif input_num == "4":
                print("正在更新配置文件...")
                response = requests.post(api_url.format(group=group, action="update-config"), params=get_params())
                print(response.text)
                input("按回车键继续...")
            elif input_num == "5":
                break
            else:
                print("输入有误，请重试。")
                input("按回车键继续...")
    elif input_num == "2":
        while True:
            group = "tasks"
            clear_screen()
            print("请选择你要管理的操作：")
            print("1. 列出最近30条任务状态")
            print("2. 列出所有任务状态（需在配置文件开启）")
            print("3. 清空任务列表")
            print("4. 返回上一级")
            input_num = input("请输入序号：")
            if input_num == "1":
                print("正在获取最近30条任务状态...")
                # GET请求
                response = requests.get(api_url.format(group=group, action="list-new"), params=get_params())
                response_json = json.loads(response.text)
                # response_json = response.json()
                for i in range(len(response_json)):
                    print(f"任务{i + 1}：ID: {response_json[f'task{i}']['id']}，状态：{response_json[f'task{i}']['status']}")
                input("按回车键继续...")
            elif input_num == "2":
                print("正在获取所有任务状态...")
                # GET请求
                response = requests.get(api_url.format(group=group, action="list-all"), params=get_params())
                response_json = json.loads(response.text)
                for i in range(len(response_json)):
                    print(f"任务{i + 1}：ID: {response_json[f'task{i}']['id']}，状态：{response_json[f'task{i}']['status']}")
                input("按回车键继续...")
            elif input_num == "3":
                print("正在清空任务列表...")
                response = requests.post(api_url.format(group=group, action="clear"), params=get_params())
                print(response.text)
                input("按回车键继续...")
            elif input_num == "4":
                break
            else:
                print("输入有误，请重试。")
    elif input_num == "3":
        while True:
            group = "blacklist"
            clear_screen()
            print("请选择你要管理的操作：")
            print("1. 列出黑名单")
            print("2. 添加到黑名单")
            print("3. 从黑名单移除")
            print("4. 清空黑名单")
            print("5. 返回上一级")
            input_num = input("请输入序号：")
            if input_num == "1":
                print("正在获取黑名单...")
                # GET请求
                response = requests.get(api_url.format(group=group, action="list"), params=get_params())
                response_json = json.loads(response.text)
                # 解析json数组
                for row in response_json:
                    print(f"IP: {row['ip']}，解除时间：{row['unblock_time']}")
                input("按回车键继续...")
            elif input_num == "2":
                while True:
                    try:
                        ip = input("请输入要添加的IP地址（按下Ctrl+C以自定义封禁时间）：")
                        unblock_time = 1
                        break
                    except KeyboardInterrupt:
                        print("请输入封禁时间（单位：小时）：")
                        unblock_time = int(input())
                print("正在添加到黑名单...")
                response = requests.post(api_url.format(group=group, action="add"),
                                         params=get_params(ip=ip, time=unblock_time))
                print(response.text)
                input("按回车键继续...")
            elif input_num == "3":
                ip = input("请输入要移除的IP地址：")
                print("正在从黑名单移除...")
                response = requests.post(api_url.format(group=group, action="remove"), params=get_params(ip=ip))
                print(response.text)
                input("按回车键继续...")
            elif input_num == "4":
                print("正在清空黑名单...")
                response = requests.post(api_url.format(group=group, action="clear"), params=get_params())
                print(response.text)
                input("按回车键继续...")
            elif input_num == "5":
                break
            else:
                print("输入有误，请重试。")
                input("按回车键继续...")
