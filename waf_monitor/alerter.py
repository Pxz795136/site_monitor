"""
告警处理模块 - 提供各种告警通知方式
"""

import requests
import json
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from abc import ABC, abstractmethod
import time
import inspect


class Alerter(ABC):
    """
    告警接口抽象基类
    """
    
    @abstractmethod
    def send_alert(self, message, level='warning'):
        """
        发送告警
        
        @param {str} message - 告警消息
        @param {str} level - 告警级别，如'info', 'warning', 'error'
        @returns {bool} 发送成功返回True，否则返回False
        """
        pass


class WechatAlerter(Alerter):
    """
    企业微信告警实现
    """
    
    def __init__(self, webhook_url, logger=None):
        """
        初始化企业微信告警器
        
        @param {str} webhook_url - 企业微信机器人的webhook URL
        @param {logging.Logger} logger - 日志记录器，如果为None则创建新的
        """
        self.webhook_url = webhook_url
        self.logger = logger or logging.getLogger(__name__)
    
    def send_alert(self, message, level='warning'):
        """
        发送企业微信告警
        
        @param {str} message - 告警消息
        @param {str} level - 告警级别，如'info', 'warning', 'error'
        @returns {bool} 发送成功返回True，否则返回False
        """
        headers = {'Content-Type': 'application/json'}
        
        # 根据告警级别添加不同的前缀
        if level == 'error':
            prefix = "🔴 严重告警"
        elif level == 'warning':
            prefix = "🟠 警告"
        else:
            prefix = "ℹ️ 通知"
        
        data = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"{prefix}\n{message}"
            }
        }
        
        try:
            response = requests.post(self.webhook_url, json=data, headers=headers, timeout=5)
            if response.status_code == 200 and response.json().get('errcode') == 0:
                self.logger.info(f"企业微信告警发送成功: {message[:100]}...")
                return True
            else:
                self.logger.error(f"企业微信告警发送失败: {response.text}")
                return False
        except Exception as e:
            self.logger.error(f"企业微信告警发送异常: {str(e)}")
            return False


class EmailAlerter(Alerter):
    """
    邮件告警实现
    """
    
    def __init__(self, smtp_server, smtp_port, sender_email, sender_password, receiver_email, 
                 site_receiver_email=None, process_receiver_email=None, logger=None):
        """
        初始化邮件告警器
        
        @param {str} smtp_server - SMTP服务器地址
        @param {int} smtp_port - SMTP服务器端口
        @param {str} sender_email - 发件人邮箱
        @param {str} sender_password - 发件人密码
        @param {str|list} receiver_email - 收件人邮箱，可以是单个字符串或邮箱列表
        @param {str|list} site_receiver_email - 站点告警专用收件人邮箱，未设置则使用receiver_email
        @param {str|list} process_receiver_email - 守护进程告警专用收件人邮箱，未设置则使用receiver_email
        @param {logging.Logger} logger - 日志记录器，如果为None则创建新的
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.logger = logger or logging.getLogger(__name__)
        
        # 处理一般收件人
        self.receiver_emails = self._process_email_list(receiver_email)
        
        # 处理站点告警专用收件人
        if site_receiver_email:
            self.site_receiver_emails = self._process_email_list(site_receiver_email)
        else:
            self.site_receiver_emails = self.receiver_emails
            
        # 处理守护进程告警专用收件人
        if process_receiver_email:
            self.process_receiver_emails = self._process_email_list(process_receiver_email)
        else:
            self.process_receiver_emails = self.receiver_emails
        
        if self.receiver_emails:
            self.logger.info(f"配置的收件人邮箱: {self.receiver_emails}")
            if site_receiver_email:
                self.logger.info(f"配置的站点告警专用收件人邮箱: {self.site_receiver_emails}")
            if process_receiver_email:
                self.logger.info(f"配置的守护进程告警专用收件人邮箱: {self.process_receiver_emails}")
        else:
            self.logger.warning("没有有效的收件人邮箱配置")
    
    def _process_email_list(self, email_input):
        """
        处理邮箱输入，返回有效邮箱列表
        
        @param {str|list} email_input - 输入的邮箱，可以是字符串或列表
        @returns {list} 有效邮箱列表
        """
        result = []
        
        if isinstance(email_input, str):
            # 如果是字符串，检查是否包含多个邮箱（以逗号或分号分隔）
            if ',' in email_input or ';' in email_input:
                # 替换所有分号为逗号，然后按逗号分割
                email_input = email_input.replace(';', ',')
                emails = [email.strip() for email in email_input.split(',') if email.strip()]
                
                # 验证每个邮箱格式
                for email in emails:
                    if '@' in email and '.' in email:  # 简单验证邮箱格式
                        result.append(email)
                    else:
                        self.logger.warning(f"忽略无效的邮箱地址: {email}")
            else:
                if '@' in email_input and '.' in email_input:  # 简单验证邮箱格式
                    result.append(email_input.strip())
                else:
                    self.logger.warning(f"忽略无效的邮箱地址: {email_input}")
        elif isinstance(email_input, list):
            # 如果已经是列表，直接使用，但验证格式
            for email in email_input:
                if isinstance(email, str) and '@' in email and '.' in email:  # 简单验证邮箱格式
                    result.append(email.strip())
                else:
                    self.logger.warning(f"忽略无效的邮箱地址: {email}")
        else:
            # 其他情况，使用空列表
            self.logger.error(f"无效的收件人格式: {email_input}")
        
        return result
    
    def send_alert(self, message, level='warning', alert_type=None):
        """
        发送邮件告警
        
        @param {str} message - 告警消息
        @param {str} level - 告警级别，如'info', 'warning', 'error'
        @param {str} alert_type - 告警类型，'site'表示站点告警，'process'表示守护进程告警，None表示一般告警
        @returns {bool} 发送成功返回True，否则返回False
        """
        # 根据告警类型选择合适的收件人列表
        if alert_type == 'site':
            receivers = self.site_receiver_emails
            type_prefix = "【站点监控】"
        elif alert_type == 'process':
            receivers = self.process_receiver_emails
            type_prefix = "【进程监控】"
        else:
            receivers = self.receiver_emails
            type_prefix = ""
        
        if not receivers:
            self.logger.error(f"没有有效的收件人，无法发送{type_prefix}邮件")
            return False
            
        # 根据告警级别设置主题
        if level == 'error':
            subject = f"{type_prefix}【严重告警】WAF监控系统告警"
        elif level == 'warning':
            subject = f"{type_prefix}【警告】WAF监控系统告警"
        else:
            subject = f"{type_prefix}【通知】WAF监控系统通知"
        
        # 尝试逐个发送给所有收件人
        success = False
        
        for receiver in receivers:
            try:
                self.logger.info(f"尝试发送{type_prefix}邮件到: {receiver}")
                
                # 为每个收件人单独创建邮件
                msg = MIMEMultipart()
                msg['From'] = self.sender_email
                msg['To'] = receiver  # 单个收件人
                msg['Subject'] = subject
                
                # 使用HTML格式以支持更好的格式化
                # 预先处理消息中的换行符
                formatted_message = message.replace('\n', '<br>')
                html_message = f"""
                <html>
                <body>
                <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px;">
                    {formatted_message}
                </div>
                </body>
                </html>
                """
                
                msg.attach(MIMEText(html_message, 'html', 'utf-8'))
                
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, [receiver], msg.as_string())
                self.logger.info(f"成功发送{type_prefix}邮件到: {receiver}")
                success = True
                
                # 关闭连接
                server.quit()
            except Exception as e:
                self.logger.error(f"发送{type_prefix}邮件到 {receiver} 失败: {str(e)}")
        
        return success


class MultiAlerter(Alerter):
    """
    多渠道告警器，可同时使用多种告警方式
    """
    
    def __init__(self, alerters=None):
        """
        初始化多渠道告警器
        
        @param {list} alerters - 告警器列表
        """
        self.alerters = alerters or []
    
    def add_alerter(self, alerter):
        """
        添加告警器
        
        @param {Alerter} alerter - 告警器实例
        """
        if isinstance(alerter, Alerter):
            self.alerters.append(alerter)
    
    def send_alert(self, message, level='warning', alert_type=None):
        """
        向所有配置的告警渠道发送告警
        
        @param {str} message - 告警消息
        @param {str} level - 告警级别，如'info', 'warning', 'error'
        @param {str} alert_type - 告警类型，'site'表示站点告警，'process'表示守护进程告警
        @returns {bool} 如果任一告警器发送成功则返回True，否则返回False
        """
        success = False
        for alerter in self.alerters:
            # 兼容已有告警器，检查是否支持alert_type参数
            if hasattr(alerter, 'send_alert') and 'alert_type' in inspect.signature(alerter.send_alert).parameters:
                if alerter.send_alert(message, level, alert_type):
                    success = True
            else:
                # 旧版告警器不支持alert_type参数
                if alerter.send_alert(message, level):
                    success = True
        return success


def create_alerter(config, logger=None):
    """
    根据配置创建合适的告警器
    
    @param {dict} config - 配置字典
    @param {logging.Logger} logger - 日志记录器
    @returns {Alerter} 告警器实例
    """
    multi_alerter = MultiAlerter()
    
    # 添加企业微信告警器（如果配置了并且开启了）
    if 'wechat_webhook_url' in config and config.get('enable_wechat_alert', True):
        wechat_alerter = WechatAlerter(config['wechat_webhook_url'], logger)
        multi_alerter.add_alerter(wechat_alerter)
    
    # 添加站点告警专用的企业微信告警器
    if 'site_wechat_webhook_url' in config and config.get('enable_site_wechat_alert', True):
        site_wechat_alerter = WechatAlerter(config['site_wechat_webhook_url'], logger)
        # 自定义send_alert方法，只处理站点告警
        original_send_alert = site_wechat_alerter.send_alert
        def site_send_alert(message, level='warning', alert_type=None):
            if alert_type == 'site' or alert_type is None:
                return original_send_alert(message, level)
            return False
        site_wechat_alerter.send_alert = site_send_alert
        multi_alerter.add_alerter(site_wechat_alerter)
    
    # 添加进程告警专用的企业微信告警器
    if 'process_wechat_webhook_url' in config and config.get('enable_process_wechat_alert', True):
        process_wechat_alerter = WechatAlerter(config['process_wechat_webhook_url'], logger)
        # 自定义send_alert方法，只处理进程告警
        original_send_alert = process_wechat_alerter.send_alert
        def process_send_alert(message, level='warning', alert_type=None):
            if alert_type == 'process' or alert_type is None:
                return original_send_alert(message, level)
            return False
        process_wechat_alerter.send_alert = process_send_alert
        multi_alerter.add_alerter(process_wechat_alerter)
    
    # 添加邮件告警器（如果配置了所有必要参数并且开启了）
    required_email_params = ['smtp_server', 'smtp_port', 'sender_email', 
                            'sender_password', 'receiver_email']
    if all(param in config for param in required_email_params) and config.get('enable_email_alert', True):
        # 获取站点告警和进程告警专用邮箱地址
        site_receiver_email = config.get('site_receiver_email')
        process_receiver_email = config.get('process_receiver_email')
        
        email_alerter = EmailAlerter(
            config['smtp_server'],
            config['smtp_port'],
            config['sender_email'],
            config['sender_password'],
            config['receiver_email'],
            site_receiver_email,
            process_receiver_email,
            logger
        )
        multi_alerter.add_alerter(email_alerter)
    
    return multi_alerter


def format_url_alert_message(url, waf_info, status_code=None, response_time=None, error=None, is_recovery=False):
    """
    格式化URL告警消息
    
    @param {str} url - 监控的URL
    @param {str} waf_info - WAF信息
    @param {int} status_code - HTTP状态码
    @param {float} response_time - 响应时间（秒）
    @param {str} error - 错误信息（如果有）
    @param {bool} is_recovery - 是否为恢复通知
    @returns {str} 格式化的告警消息
    """
    current_time = time.strftime('%Y-%m-%d %H:%M:%S')
    status_text = '🔴 不健康' if status_code != 200 or error or (response_time and response_time > 5) else '✅ 健康'
    
    # 预先格式化响应时延部分，避免嵌套f-string
    if response_time is None:
        response_time_text = 'N/A'
    else:
        response_time_text = f'{response_time:.6f}s'
    
    # 预先格式化状态码部分
    status_code_text = 'N/A' if status_code is None else str(status_code)
    
    # 为恢复通知添加特殊标记
    title = "站点监控告警"
    if is_recovery:
        title = "站点监控通知 (已恢复正常)"
    
    message = f"""## {title} - {current_time}
**网站URL**：{url}
**所在WAF**：{waf_info}
**状态码**：{status_code_text}
**响应时延**：{response_time_text}
**状态**：{status_text}"""
    
    if error:
        message += f"\n**异常信息**：{error}"
    
    return message


def format_process_alert_message(group_name, pid, status, error=None, restart_attempt=None):
    """
    格式化进程告警消息
    
    @param {str} group_name - 监控组名称
    @param {int} pid - 进程ID
    @param {str} status - 进程状态
    @param {str} error - 错误信息（如果有）
    @param {int} restart_attempt - 重启尝试次数（如果有）
    @returns {str} 格式化的告警消息
    """
    current_time = time.strftime('%Y-%m-%d %H:%M:%S')
    
    message = f"""## 进程监控告警 - {current_time}
**监控组**：{group_name}
**进程ID**：{pid}
**状态**：{status}"""
    
    if error:
        message += f"\n**错误信息**：{error}"
    
    if restart_attempt is not None:
        message += f"\n**重启尝试**：第{restart_attempt}次"
    
    return message 