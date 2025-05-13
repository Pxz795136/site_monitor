"""
监控核心逻辑模块 - 提供URL健康检查功能
"""

import requests
import threading
import time
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from . import utils
from . import alerter


class URLMonitor:
    """
    URL监控器类，负责检查URL健康状态并发送告警
    """
    
    def __init__(self, group_name, config, loggers, alerter_instance):
        """
        初始化URL监控器
        
        @param {str} group_name - 监控组名称
        @param {dict} config - 配置信息
        @param {dict} loggers - 日志记录器字典
        @param {alerter.Alerter} alerter_instance - 告警器实例
        """
        self.group_name = group_name
        self.config = config
        self.loggers = loggers
        self.alerter = alerter_instance
        
        # 从配置中获取参数
        self.monitor_interval = config.get('monitor_interval', 60)
        self.unhealthy_threshold = config.get('unhealthy_threshold', 3)
        self.response_timeout = config.get('response_timeout', 5)
        
        # URL健康状态
        self.url_health = {}
        self.url_to_waf = {}
        
        # 线程锁
        self.lock = threading.Lock()
        
        # 运行标志
        self.running = True
    
    def load_targets(self):
        """
        加载监控目标
        
        @returns {list} URL列表
        """
        try:
            urls, url_to_waf = utils.load_config(self.group_name, 'targets')
            self.url_to_waf = url_to_waf
            return urls
        except Exception as e:
            self.loggers['monitor'].error(f"加载目标文件失败: {str(e)}")
            return []
    
    def load_state(self):
        """
        加载健康状态
        """
        state = utils.load_state(self.group_name)
        if state:
            self.loggers['monitor'].info(f"已加载持久化的健康状态")
            self.url_health = state
        else:
            self.loggers['monitor'].info(f"未找到持久化的健康状态文件，将创建新的")
    
    def save_state(self):
        """
        保存健康状态
        """
        utils.save_state(self.group_name, self.url_health)
    
    def check_health(self, url):
        """
        检查URL健康状态
        
        @param {str} url - 要检查的URL
        """
        try:
            response = requests.get(url, timeout=self.response_timeout)
            status_code = response.status_code
            response_time = response.elapsed.total_seconds()
            
            waf_info = self.url_to_waf.get(url, "未知WAF")
            
            if status_code != 200 or response_time > self.response_timeout:
                with self.lock:
                    self.url_health[url]['count'] += 1
                    need_alert = self.url_health[url]['count'] % self.unhealthy_threshold == 0
                    current_count = self.url_health[url]['count']
                    # 在锁内更新告警状态
                    if need_alert:
                        self.url_health[url]['alerted'] = True
                
                # 锁外执行日志记录和告警发送
                alert_message = alerter.format_url_alert_message(
                    url, waf_info, status_code, response_time
                )
                self.loggers['monitor'].warning(
                    f"URL不健康: {url}, 状态码: {status_code}, 响应时间: {response_time:.6f}s"
                )
                self.loggers['unhealthy'].warning(alert_message)
                
                # 连续不健康次数达到阈值时发送告警
                if need_alert:
                    self.alerter.send_alert(alert_message, 'warning', alert_type='site')
                    self.loggers['alert'].warning(
                        f"URL已连续 {current_count} 次不健康，已发送告警: {url}"
                    )
            else:
                with self.lock:
                    # 检查是否之前状态为告警，需要发送恢复通知
                    was_alerted = self.url_health[url]['alerted']
                    # 更新状态
                    self.url_health[url]['count'] = 0
                    self.url_health[url]['alerted'] = False
                
                # 锁外执行日志记录
                self.loggers['health'].info(
                    f"URL健康: {url}, 状态码: {status_code}, 响应时间: {response_time:.6f}s"
                )
                
                # 如果之前发送过告警，现在恢复健康，则发送恢复通知
                if was_alerted:
                    recovery_message = alerter.format_url_alert_message(
                        url, waf_info, status_code, response_time, is_recovery=True
                    )
                    self.alerter.send_alert(recovery_message, 'info', alert_type='site')
                    self.loggers['alert'].info(f"URL已恢复正常: {url}")
        
        except Exception as e:
            with self.lock:
                self.url_health[url]['count'] += 1
                need_alert = self.url_health[url]['count'] % self.unhealthy_threshold == 0
                current_count = self.url_health[url]['count']
                # 在锁内更新告警状态
                if need_alert:
                    self.url_health[url]['alerted'] = True
            
            # 锁外执行日志记录和告警发送
            waf_info = self.url_to_waf.get(url, "未知WAF")
            alert_message = alerter.format_url_alert_message(
                url, waf_info, error=str(e)
            )
            self.loggers['monitor'].warning(f"URL检查异常: {url}, 错误: {str(e)}")
            self.loggers['unhealthy'].warning(alert_message)
            
            # 连续不健康次数达到阈值时发送告警
            if need_alert:
                self.alerter.send_alert(alert_message, 'warning', alert_type='site')
                self.loggers['alert'].warning(
                    f"URL已连续 {current_count} 次不健康，已发送告警: {url}"
                )
    
    def monitor_urls(self):
        """
        监控所有URL
        """
        self.loggers['monitor'].info("开始URL监控")
        
        # 加载持久化的健康状态
        self.load_state()
        
        with ThreadPoolExecutor(max_workers=min(32, os.cpu_count() * 4 or 4)) as executor:
            while self.running:
                try:
                    # 重新加载配置
                    try:
                        global_config = utils.load_global_config()
                        group_config = utils.load_config(self.group_name)
                        config = utils.merge_configs(global_config, group_config)
                        
                        # 更新配置参数
                        old_interval = self.monitor_interval
                        old_threshold = self.unhealthy_threshold
                        old_timeout = self.response_timeout
                        
                        self.monitor_interval = config.get('monitor_interval', 60)
                        self.unhealthy_threshold = config.get('unhealthy_threshold', 3)
                        self.response_timeout = config.get('response_timeout', 5)
                        
                        # 根据当前配置更新告警器
                        self.alerter = alerter.create_alerter(config, self.loggers.get('alert'))
                        
                        # 如果配置发生变化，记录日志
                        if (old_interval != self.monitor_interval or 
                            old_threshold != self.unhealthy_threshold or 
                            old_timeout != self.response_timeout):
                            self.loggers['monitor'].info(
                                f"配置已更新: 监控间隔={self.monitor_interval}秒, "
                                f"不健康阈值={self.unhealthy_threshold}次, "
                                f"响应超时={self.response_timeout}秒"
                            )
                    except Exception as e:
                        self.loggers['monitor'].error(f"重新加载配置失败: {str(e)}")
                    
                    # 重新加载URL列表
                    urls = self.load_targets()
                    if not urls:
                        self.loggers['monitor'].warning("没有找到有效的URL，将在下次循环重试")
                        time.sleep(self.monitor_interval)
                        continue
                    
                    self.loggers['monitor'].info(f"已加载 {len(urls)} 个URL")
                    
                    # 更新URL健康状态字典
                    with self.lock:
                        # 删除不再监控的URL
                        for url in list(self.url_health.keys()):
                            if url not in urls:
                                del self.url_health[url]
                        
                        # 添加新的URL
                        for url in urls:
                            if url not in self.url_health:
                                self.url_health[url] = {'count': 0, 'alerted': False}
                    
                    # 并行检查所有URL
                    futures = [executor.submit(self.check_health, url) for url in urls]
                    for future in futures:
                        future.result()  # 等待所有检查完成
                    
                    # 保存健康状态
                    self.save_state()
                    
                    # 等待下一次监控循环
                    time.sleep(self.monitor_interval)
                
                except Exception as e:
                    self.loggers['monitor'].error(f"监控循环出现异常: {str(e)}")
                    # 添加重试计数和退避时间
                    retry_count = getattr(self, '_retry_count', 0) + 1
                    self._retry_count = retry_count
                    # 计算退避时间，最长不超过5分钟
                    backoff_time = min(300, 10 * (2 ** (retry_count - 1)))
                    self.loggers['monitor'].info(f"将在 {backoff_time} 秒后重试 (第 {retry_count} 次)")
                    time.sleep(backoff_time)
                else:
                    # 成功执行后重置重试计数
                    self._retry_count = 0
    
    def start(self):
        """
        启动监控
        """
        self.running = True
        threading.Thread(target=self.monitor_urls, daemon=True).start()
    
    def stop(self):
        """
        停止监控
        """
        self.running = False


def create_monitor(group_name):
    """
    创建并配置监控器
    
    @param {str} group_name - 监控组名称
    @returns {URLMonitor} 配置好的监控器实例
    """
    # 加载配置
    try:
        global_config = utils.load_global_config()
        group_config = utils.load_config(group_name)
        config = utils.merge_configs(global_config, group_config)
    except Exception as e:
        print(f"加载配置失败: {str(e)}")
        raise
    
    # 设置日志
    try:
        loggers = utils.setup_logging(group_name, ['monitor', 'health', 'unhealthy', 'alert'])
    except Exception as e:
        print(f"设置日志失败: {str(e)}")
        raise
    
    # 创建告警器
    try:
        alerter_instance = alerter.create_alerter(config, loggers.get('alert'))
    except Exception as e:
        loggers['monitor'].error(f"创建告警器失败: {str(e)}")
        raise
    
    # 创建监控器
    try:
        monitor = URLMonitor(group_name, config, loggers, alerter_instance)
        return monitor
    except Exception as e:
        loggers['monitor'].error(f"创建监控器失败: {str(e)}")
        raise 