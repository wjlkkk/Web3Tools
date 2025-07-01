import requests
import random
import string
import datetime
import time
import urllib3
import logging
import schedule
from DrissionPage import ChromiumPage, ChromiumOptions
from threading import Lock

# 禁用 SSL 验证警告
urllib3.disable_warnings()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

# 全局变量
total_request_count = 0
request_count_lock = Lock()
success_email_file = "success_emails.txt"  # 成功邮箱记录文件

# API 地址
url = "https://shelby.xyz/api/hubspot-contact"
token_url = "https://shelby.xyz"

def generate_random_part(length=6):
    """生成指定长度的随机字母和数字组合"""
    characters = string.ascii_lowercase + string.digits
    return ''.join(random.choices(characters, k=length))

def generate_email(domain="kkkruis.uu.me"):
    """生成单个邮箱并返回，失败返回None"""
    uu_url = "https://api.uu.me/v1/addr/update"
    header = {"authorization": "Bearer 9337a31c2bd976f4177a8f49039e75617ade7ef0f8d419338c97711fa49720dea66ca6dca9a3d7ed51f63313e64a6f6b"}
    alias = generate_random_part()
    payload = {"alias": alias}
    
    try:
        response = requests.post(uu_url, data=payload, headers=header)
        if response.status_code == 200:
            email = f"{alias}@{domain}"
            logging.info(f"✅ 邮箱生成成功: {email}")
            return email
        else:
            logging.error(f"❌ 生成邮箱失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logging.exception("❌ 生成邮箱异常")
        return None

def get_turnstile_token(url):
    """
    获取新的 Turnstile Token（每次调用生成新 token）
    :param url: 目标页面 URL
    :return: token 字符串
    """
    logging.info("🔄 正在获取新的 Turnstile Token...")

    co = ChromiumOptions().headless(False)
    page = ChromiumPage(co)

    try:
        page.get(url)
        time.sleep(5)  # 等待验证码加载

        logging.info("⏳ 等待 cf-turnstile-response 字段出现...")
        page.wait.ele_displayed('@name=cf-turnstile-response', timeout=30)

        script = "return document.querySelector(\"input[name='cf-turnstile-response']\").value;"
        token = page.run_js(script)

        if token:
            logging.info("✅ 成功获取 Turnstile Token")
        else:
            logging.error("❌ 获取 Turnstile Token 失败，值为空")
    finally:
        page.quit()

    return token

def log_success_email(email, status_code, response_text):
    """
    将成功发送的邮箱、时间、结果记录到文件
    :param email: 发送成功的邮箱
    :param status_code: HTTP 状态码
    :param response_text: 响应内容
    """
    try:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{current_time}] 邮箱: {email} | 状态码: {status_code} | 响应: {response_text}\n"
        
        with open(success_email_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
        logging.info(f"💾 邮箱已记录: {email} | 状态码: {status_code}")
    except Exception as e:
        logging.error(f"❌ 记录邮箱失败: {email} - {str(e)}")

def send_request(session):
    """
    生成邮箱并发送请求
    """
    global total_request_count
    
    # 生成邮箱
    email = generate_email()
    if not email:
        logging.warning("⚠️ 邮箱生成失败，跳过请求")
        return
    
    # 获取 Turnstile Token
    token = get_turnstile_token(token_url)
    if not token:
        logging.warning("⚠️ 无法获取有效 Token，跳过请求")
        return

    # 构造请求
    payload = {
        "email": email,
        "extra_field": "",
        "form_timestamp": int(datetime.datetime.utcnow().timestamp()),
        "turnstileToken": token
    }

    try:
        response = session.post(url, json=payload, verify=False)
        if response.status_code == 200:
            with request_count_lock:
                global total_request_count
                total_request_count += 1
                current_count = total_request_count
            logging.info(f"📧 请求成功: {email} | 当前总请求数: {current_count}")
            log_success_email(email, response.status_code, response.text)  # 记录邮箱、状态码、响应
        else:
            logging.error(f"❌ 请求失败: {email} | 状态码: {response.status_code} - {response.text}")
    except Exception as e:
        logging.error(f"❌ 请求失败: {email} - {str(e)}")

def scheduled_job(session):
    """定时任务：生成邮箱并发送请求"""
    logging.info("⏰ 开始执行定时任务")
    send_request(session)

def main():
    # 初始化Session
    session = requests.Session()
    session.verify = False

    # 安排定时任务（每 6 秒执行一次，每分钟 10 次请求）
    schedule.every(6).seconds.do(scheduled_job, session=session)

    logging.info("🟢 开始执行定时任务（每分钟 10 个请求）")
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()