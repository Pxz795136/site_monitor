import requests
from concurrent.futures import ThreadPoolExecutor
import threading
import time
import logging
import json

# 从配置文件中读取配置
with open('config.json', 'r') as file:
    config = json.load(file)

wechat_webhook_url = config['wechat_webhook_url']
monitor_interval = config['monitor_interval']
unhealthy_threshold = config['unhealthy_threshold']
response_timeout = config['response_timeout']  # 从config中读取响应超时时间

class AlertHandler:
    def __init__(self, wechat_webhook_url):
        self.wechat_webhook_url = wechat_webhook_url

    def send_wechat_alert(self, message):
        headers = {'Content-Type': 'application/json'}
        data = {
            "msgtype": "markdown",
            "markdown": {
                "content": message
            }
        }
        requests.post(self.wechat_webhook_url, json=data, headers=headers)

    def send_alert(self, message):
        self.send_wechat_alert(message)

url_health = {}
url_to_waf = {}  # Store URL to WAF mappings
lock = threading.Lock()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
health_logger = logging.getLogger("HealthLogger")
unhealthy_logger = logging.getLogger("UnhealthyLogger")

health_handler = logging.FileHandler('health.log')
health_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
health_logger.addHandler(health_handler)

unhealthy_handler = logging.FileHandler('unhealthy.log')
unhealthy_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
unhealthy_logger.addHandler(unhealthy_handler)

def format_alert_message(url, status_code=None, response_time=None, error=None):
    waf_info = url_to_waf.get(url, "未知WAF")
    status_text = '🔴 不健康' if status_code != 200 or response_time > response_timeout else '✅ 健康'
    alert_message = f"""## 告警时间：{time.strftime('%Y-%m-%d %H:%M:%S')}
**网站URL**：{url}
**所在WAF**：{waf_info}
**状态码**：{'N/A' if status_code is None else status_code}
**响应时延**：{'N/A' if response_time is None else f'{response_time:.6f}s'}
**状态**：{status_text}"""
    if error:
        alert_message += f"\n**异常信息**：{error}"
    return alert_message

def check_health(url):
    try:
        response = requests.get(url, timeout=response_timeout)
        status_code = response.status_code
        response_time = response.elapsed.total_seconds()
        alert_message = format_alert_message(url, status_code, response_time)

        if status_code != 200 or response_time > response_timeout:
            with lock:
                url_health[url]['count'] += 1
                unhealthy_logger.warning(alert_message)
                if url_health[url]['count'] % unhealthy_threshold == 0:
                    alert_handler.send_alert(alert_message)
        else:
            with lock:
                health_log_message = f"网站健康：{url}\n状态码：{status_code}\n响应时延：{response_time:.6f}s"
                if url_health[url]['alerted']:
                    recovery_message = f"网站已恢复正常：{url}\n状态码：{status_code}\n响应时延：{response_time:.6f}s"
                    health_logger.info(recovery_message)
                    alert_handler.send_alert(recovery_message)
                else:
                    health_logger.info(health_log_message)
                url_health[url]['count'] = 0
                url_health[url]['alerted'] = False
    except Exception as e:
        with lock:
            url_health[url]['count'] += 1
            alert_message = format_alert_message(url, error=str(e))
            unhealthy_logger.warning(alert_message)
            if url_health[url]['count'] % unhealthy_threshold == 0:
                alert_handler.send_alert(alert_message)

url_health_filename = 'url_health.json'

def save_url_health():
    with open(url_health_filename, 'w') as file:
        json.dump(url_health, file)

def load_url_health():
    try:
        with open(url_health_filename, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return None

def load_url_list(file_path):
    urls = []
    with open(file_path, 'r') as file:
        for line in file:
            line = line.strip()
            if line.startswith('#'):  # 忽略整行注释
                continue
            parts = line.split(';')  # 使用分号分隔URL和WAF信息
            url = parts[0].strip()
            waf = parts[1].strip() if len(parts) > 1 else "未知WAF"
            url_to_waf[url] = waf
            urls.append(url)
    return urls

def monitor_urls_with_threadpool_and_persistence(interval):
    with ThreadPoolExecutor() as executor:
        while True:
            new_urls = load_url_list('input.txt')  # 重新加载URL列表
            for url in list(url_health.keys()):
                if url not in new_urls:
                    del url_health[url]
            for url in new_urls:
                if url not in url_health:
                    url_health[url] = {'count': 0, 'alerted': False}
            futures = [executor.submit(check_health, url) for url in new_urls]
            for future in futures:
                future.result()
            save_url_health()
            time.sleep(interval)

if __name__ == "__main__":
    alert_handler = AlertHandler(wechat_webhook_url)
    loaded_url_health = load_url_health()
    if loaded_url_health:
        url_health.update(loaded_url_health)
    monitor_urls_with_threadpool_and_persistence(monitor_interval)
