"""
脚本运行监控模块 - 监控各监控进程的运行状态并自动恢复
"""

import os
import time
import logging
import subprocess
import json
import signal
import sys
import psutil
from datetime import datetime
from . import utils
from . import alerter


class ProcessInfo:
    """
    进程信息类，存储进程的各种状态信息
    """
    def __init__(self, group_name, pid=None, status="未知", restart_count=0, 
                 last_check_time=None, last_start_time=None, was_restarted=False, need_alert=True):
        self.group_name = group_name
        self.pid = pid
        self.status = status  # 状态: 运行中, 已停止, 未知
        self.restart_count = restart_count  # 重启次数
        self.last_check_time = last_check_time or datetime.now()
        self.last_start_time = last_start_time or datetime.now()
        self.was_restarted = was_restarted  # 是否是由watchdog重启的
        self.need_alert = need_alert  # 是否需要发送告警
    
    def to_dict(self):
        """转换为字典表示"""
        return {
            'group_name': self.group_name,
            'pid': self.pid,
            'status': self.status,
            'restart_count': self.restart_count,
            'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
            'last_start_time': self.last_start_time.isoformat() if self.last_start_time else None,
            'was_restarted': self.was_restarted,
            'need_alert': self.need_alert
        }
    
    @classmethod
    def from_dict(cls, data):
        """从字典创建实例"""
        return cls(
            group_name=data['group_name'],
            pid=data['pid'],
            status=data['status'],
            restart_count=data['restart_count'],
            last_check_time=datetime.fromisoformat(data['last_check_time']) if data.get('last_check_time') else None,
            last_start_time=datetime.fromisoformat(data['last_start_time']) if data.get('last_start_time') else None,
            was_restarted=data.get('was_restarted', False),
            need_alert=data.get('need_alert', True)
        )


class Watchdog:
    """
    监控进程运行状态，自动重启异常退出的进程
    """
    
    def __init__(self, groups=None, check_interval=60, max_restarts=5, logger=None, alerter_instance=None):
        """
        初始化监控器
        
        @param {list} groups - 监控组列表
        @param {int} check_interval - 检查间隔，单位秒
        @param {int} max_restarts - 最大自动重启次数
        @param {logging.Logger} logger - 日志记录器
        @param {alerter.Alerter} alerter_instance - 告警器实例
        """
        self.groups = groups or []
        self.check_interval = check_interval
        self.max_restarts = max_restarts
        self.logger = logger or logging.getLogger("watchdog")
        self.alerter = alerter_instance
        
        # 进程信息字典，键为组名，值为ProcessInfo实例
        self.processes = {}
        
        # 运行标志
        self.running = False
        
        # 加载持久化的进程信息
        self.load_state()
    
    def load_state(self):
        """
        加载进程状态信息
        """
        try:
            project_root = utils.get_project_root()
            state_file = os.path.join(project_root, 'data', 'watchdog.json')
            
            if os.path.exists(state_file):
                with open(state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for group_name, process_data in data.items():
                        self.processes[group_name] = ProcessInfo.from_dict(process_data)
                self.logger.info("[系统初始化] 已加载持久化的进程状态信息")
        except Exception as e:
            self.logger.error(f"[系统错误] 加载进程状态信息失败: {str(e)}")
    
    def save_state(self):
        """
        保存进程状态信息
        """
        try:
            project_root = utils.get_project_root()
            state_file = os.path.join(project_root, 'data', 'watchdog.json')
            
            with open(state_file, 'w', encoding='utf-8') as f:
                data = {group: process.to_dict() for group, process in self.processes.items()}
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"[系统错误] 保存进程状态信息失败: {str(e)}")
    
    def check_process(self, group_name):
        """
        检查指定组的进程状态
        
        @param {str} group_name - 监控组名称
        @returns {bool} 进程是否正常运行
        """
        pid = utils.load_pid(group_name)
        
        # 如果进程信息不存在，初始化它
        if group_name not in self.processes:
            self.processes[group_name] = ProcessInfo(group_name, pid)
        
        # 检查PID是否变化，如果变化了可能是被手动重启了
        old_pid = self.processes[group_name].pid
        if pid is not None and old_pid is not None and pid != old_pid:
            # PID变化说明进程被手动重启，重置重启计数
            self.logger.info(f"检测到 {group_name} 进程PID变更 ({old_pid} -> {pid})，可能是手动重启，重置重启计数")
            self.processes[group_name].restart_count = 0
        
        # 更新PID
        self.processes[group_name].pid = pid
        self.processes[group_name].last_check_time = datetime.now()
        
        # 检查进程是否存在
        if pid is None:
            # 检查数据目录中是否存在PID文件，如果存在但内容为空或无效，则移除它
            pid_file = os.path.join(utils.get_project_root(), 'data', f"{group_name}.pid")
            if os.path.exists(pid_file):
                try:
                    os.remove(pid_file)
                    self.logger.info(f"[系统维护] 已清理无效PID文件: {pid_file}")
                except Exception as e:
                    self.logger.error(f"[系统错误] 删除PID文件失败: {str(e)}")
            
            # 检查当前状态和上一次状态，判断是否是手动停止
            current_status = self.processes[group_name].status
            
            # 如果状态已经是"已停止"而不是"未知"，可能是手动停止的
            # 或者状态包含"手动停止"字样，也判断为手动停止
            if (current_status == "已停止" or 
                "手动停止" in current_status):
                self.processes[group_name].status = "已手动停止"
                self.logger.info(f"[正常状态] 进程 {group_name} 处于手动停止状态，无需重启和告警")
                # 标记不需要告警和重启
                self.processes[group_name].need_alert = False
            else:
                self.processes[group_name].status = "已停止"
            
            return False
        
        # 使用psutil更严格地检查进程是否真的在运行
        try:
            process = psutil.Process(pid)
            
            # 检查进程命令行来验证这确实是我们的监控进程
            cmdline = process.cmdline()
            monitor_script_name = f"monitor_{group_name}.py"
            
            # 如果进程存在但不是我们的监控进程，删除PID文件并报告不存在
            if not any(monitor_script_name in cmd for cmd in cmdline):
                self.logger.info(f"[系统维护] 清理过期PID文件: PID {pid} 已不再与 {group_name} 监控进程关联")
                pid_file = os.path.join(utils.get_project_root(), 'data', f"{group_name}.pid")
                if os.path.exists(pid_file):
                    try:
                        os.remove(pid_file)
                    except Exception as e:
                        self.logger.error(f"[系统错误] 删除PID文件失败: {str(e)}")
                
                self.processes[group_name].status = "已停止"
                return False
                
            # 确认是我们的监控进程，并且正在运行
            self.logger.debug(f"[正常状态] 进程 {group_name} 正常运行中，PID: {pid}")
            
            # 如果进程从已停止状态变为运行中，可能是被手动启动，重置重启计数
            if self.processes[group_name].status == "已停止" or self.processes[group_name].status == "已停止 - 超过最大重启次数" or self.processes[group_name].status == "已手动停止":
                self.logger.info(f"检测到 {group_name} 进程从已停止状态变为运行中，可能是手动启动，重置重启计数")
                self.processes[group_name].restart_count = 0
                self.processes[group_name].need_alert = True  # 恢复告警标志
            
            self.processes[group_name].status = "运行中"
            return True
            
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            self.logger.warning(f"检查进程 {pid} 时出错: {str(e)}")
            
            # PID文件存在但进程不存在或无法访问，删除PID文件
            pid_file = os.path.join(utils.get_project_root(), 'data', f"{group_name}.pid")
            if os.path.exists(pid_file):
                try:
                    os.remove(pid_file)
                    self.logger.info(f"已删除无效的PID文件: {pid_file}")
                except Exception as e_file:
                    self.logger.error(f"删除PID文件失败: {str(e_file)}")
            
            self.processes[group_name].status = "已停止"
            return False
    
    def restart_process(self, group_name):
        """
        重启指定组的进程
        
        @param {str} group_name - 监控组名称
        @returns {bool} 重启是否成功
        """
        try:
            # 首先检查是否真的需要重启
            # 如果进程状态是"已停止"但在watchdog.json中的记录是刚刚更新的，
            # 可能是因为进程刚刚正常重启，这种情况不应该发送告警
            current_time = datetime.now()
            need_alert = True
            
            if group_name in self.processes:
                last_check = self.processes[group_name].last_check_time
                # 如果最后检查时间是在最近60秒内，且状态是"已停止"
                # 那么可能是正常启动过程中的状态检查，不需要告警
                if (current_time - last_check).total_seconds() < 60:
                    self.logger.info(f"[正常状态] 进程 {group_name} 处于正常启动流程中，不发送告警")
                    need_alert = False
            
            # 增加重启计数
            if group_name in self.processes:
                self.processes[group_name].restart_count += 1
                self.processes[group_name].last_start_time = current_time
                # 记录这是一次真正的重启，用于后续告警判断
                self.processes[group_name].was_restarted = True
            
            # 执行启动命令
            project_root = utils.get_project_root()
            script_path = os.path.join(project_root, 'bin', f'monitor_{group_name}.py')
            
            self.logger.info(f"[系统操作] 正在重启 {group_name} 监控进程...")
            
            # 使用 Python 解释器执行脚本
            python_executable = sys.executable
            cmd = [python_executable, script_path]
            
            # 在后台启动进程
            with open(os.devnull, 'w') as devnull:
                process = subprocess.Popen(
                    cmd,
                    stdout=devnull,
                    stderr=devnull,
                    start_new_session=True,
                    cwd=project_root
                )
            
            self.logger.info(f"[系统操作] 已重启进程 {group_name}，新PID: {process.pid}")
            
            # 等待片刻确认进程已启动
            time.sleep(2)
            
            # 检查进程是否成功启动
            restart_success = utils.is_process_running(process.pid)
            
            # 设置一个标志，指示这次重启是否应该触发告警
            # 将这个标志保存在进程信息中
            if group_name in self.processes:
                self.processes[group_name].need_alert = need_alert and restart_success
            
            return restart_success
            
        except Exception as e:
            self.logger.error(f"[系统错误] 重启进程 {group_name} 失败: {str(e)}")
            return False
    
    def check_all_processes(self):
        """
        检查所有监控组的进程状态
        """
        self.logger.info("[系统操作] 开始检查所有进程状态")
        
        status_summary = []
        
        for group_name in self.groups:
            try:
                is_running = self.check_process(group_name)
                
                if not is_running:
                    # 获取进程信息
                    process_info = self.processes.get(group_name)
                    
                    # 如果进程被标记为手动停止，则跳过后续的重启和告警处理
                    if process_info and process_info.status == "已手动停止":
                        self.logger.info(f"[正常状态] 进程 {group_name} 为正常的停止状态，无需操作")
                        status_summary.append(f"{group_name}[已停止-正常]")
                        continue
                    
                    self.logger.info(f"[系统状态] 检测到进程 {group_name} 未运行")
                    
                    # 检查是否超过最大重启次数
                    if process_info and process_info.restart_count >= self.max_restarts:
                        # 记录更详细的进程状态信息，帮助诊断
                        self.logger.error(
                            f"[系统警告] 进程 {group_name} 超过最大重启次数 {self.max_restarts}，"
                            f"当前重启次数: {process_info.restart_count}，"
                            f"最后检查时间: {process_info.last_check_time}，"
                            f"最后启动时间: {process_info.last_start_time}，"
                            f"当前状态: {process_info.status}"
                        )
                        
                        # 添加更明确的状态
                        self.processes[group_name].status = "已停止 - 超过最大重启次数"
                        status_summary.append(f"{group_name}[已停止-失败]")
                        
                        message = alerter.format_process_alert_message(
                            group_name,
                            process_info.pid,
                            "已停止 - 超过最大重启次数",
                            restart_attempt=process_info.restart_count
                        )
                        if self.alerter:
                            self.alerter.send_alert(message, 'error', alert_type='process')
                    else:
                        # 只有当进程需要告警时才尝试重启
                        if process_info and process_info.need_alert:
                            # 尝试重启
                            restart_result = self.restart_process(group_name)
                            
                            # 获取更新后的进程信息
                            updated_process_info = self.processes.get(group_name)
                            
                            # 只有当进程真正需要告警时才发送
                            if restart_result and updated_process_info and updated_process_info.need_alert:
                                self.logger.info(f"[系统状态] 进程 {group_name} 重启成功并已发送告警")
                                message = alerter.format_process_alert_message(
                                    group_name,
                                    updated_process_info.pid,
                                    "已自动重启",
                                    restart_attempt=updated_process_info.restart_count
                                )
                                if self.alerter:
                                    self.logger.info(f"[系统操作] 为进程 {group_name} 发送告警通知")
                                    self.alerter.send_alert(message, 'warning', alert_type='process')
                            elif not restart_result:
                                # 重启失败总是需要告警
                                message = alerter.format_process_alert_message(
                                    group_name,
                                    process_info.pid if process_info else None,
                                    "重启失败",
                                    restart_attempt=process_info.restart_count if process_info else 1
                                )
                                if self.alerter:
                                    self.alerter.send_alert(message, 'warning', alert_type='process')
                            else:
                                self.logger.info(f"[正常状态] 进程 {group_name} 重启成功但不需要告警（可能是正常启动流程）")
                                status_summary.append(f"{group_name}[已重启-正常]")
                        else:
                            self.logger.info(f"[正常状态] 进程 {group_name} 当前为已停止状态（正常），无需重启")
                            status_summary.append(f"{group_name}[已停止-正常]")
                else:
                    status_summary.append(f"{group_name}[运行中]")
            
            except Exception as e:
                self.logger.error(f"[系统错误] 检查进程 {group_name} 状态时出错: {str(e)}")
                status_summary.append(f"{group_name}[检查失败]")
        
        # 保存进程状态
        self.save_state()
        
        # 添加状态总结日志
        if status_summary:
            self.logger.info(f"[系统状态] 监控进程当前状态: {', '.join(status_summary)}")
        
        self.logger.info("[系统操作] 完成检查所有进程状态")
        
        # 返回调用者是否应该继续
        return self.running
    
    def monitor(self):
        """
        开始监控所有进程 - 此方法保留用于兼容性，但现在在bin/watchdog.py中直接使用check_all_processes
        """
        self.logger.warning("[系统警告] 使用已弃用的monitor()方法，请使用bin/watchdog.py中的新实现")
        self.logger.info("[系统操作] 启动进程监控")
        self.running = True
        
        try:
            while self.running:
                self.check_all_processes()
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            self.logger.info("[系统操作] 收到中断信号，停止监控")
        except Exception as e:
            self.logger.error(f"[系统错误] 监控循环出现异常: {str(e)}")
        finally:
            self.save_state()
    
    def stop(self):
        """
        停止监控
        """
        self.running = False
        self.logger.info("[系统操作] 停止进程监控")


def create_watchdog(config=None):
    """
    创建并配置监控器
    
    @param {dict} config - 配置信息
    @returns {Watchdog} 配置好的监控器实例
    """
    if config is None:
        try:
            config = utils.load_global_config()
        except Exception as e:
            print(f"[系统错误] 加载全局配置失败: {str(e)}")
            config = {}
    
    # 设置日志
    project_root = utils.get_project_root()
    logs_dir = os.path.join(project_root, 'logs', 'watchdog')
    os.makedirs(logs_dir, exist_ok=True)
    
    logger = logging.getLogger("watchdog")
    logger.setLevel(logging.INFO)
    
    # 清除已有的处理器
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 添加文件处理器
    log_file = os.path.join(logs_dir, 'watchdog.log')
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file,
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # 添加控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 如果存在watchdog专用的配置，创建新的配置字典
    watchdog_config = config.copy()
    if 'watchdog_wechat_webhook_url' in config:
        watchdog_config['wechat_webhook_url'] = config['watchdog_wechat_webhook_url']
    
    if 'watchdog_receiver_email' in config:
        watchdog_config['receiver_email'] = config['watchdog_receiver_email']
    
    # 创建告警器
    alerter_instance = alerter.create_alerter(watchdog_config, logger)
    if alerter_instance and 'receiver_email' in watchdog_config:
        logger.info(f"[系统初始化] 配置的收件人邮箱: {watchdog_config.get('receiver_email', [])}")
    
    # 监控组列表
    groups = config.get('monitor_groups', ['group1', 'group2', 'group3', 'group4'])
    logger.info(f"[系统初始化] 配置的监控组: {groups}")
    
    # 其他配置参数
    check_interval = config.get('watchdog_check_interval', 60)
    max_restarts = config.get('watchdog_max_restarts', 5)
    logger.info(f"[系统初始化] 配置的检查间隔: {check_interval}秒, 最大重启次数: {max_restarts}")
    
    logger.info("[系统初始化] 启动进程监控")
    
    return Watchdog(
        groups=groups,
        check_interval=check_interval,
        max_restarts=max_restarts,
        logger=logger,
        alerter_instance=alerter_instance
    ) 