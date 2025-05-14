#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
崩溃处理模块 - 捕获和记录程序崩溃原因
"""

import os
import sys
import time
import signal
import traceback
import threading
import json
import logging
import atexit
import datetime
import psutil
import io

from . import utils


def setup_crash_logging(group_name):
    """
    设置崩溃日志记录器
    
    @param {str} group_name - 监控组名称
    @returns {logging.Logger} 崩溃日志记录器
    """
    project_root = utils.get_project_root()
    logs_dir = os.path.join(project_root, 'logs', group_name)
    os.makedirs(logs_dir, exist_ok=True)
    
    crash_logger = logging.getLogger(f"{group_name}_crash")
    crash_logger.setLevel(logging.INFO)
    
    # 清除已有的处理器，避免重复
    for handler in crash_logger.handlers[:]:
        crash_logger.removeHandler(handler)
    
    # 文件处理器，使用RotatingFileHandler进行日志轮转
    log_file = os.path.join(logs_dir, "crash.log")
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    crash_logger.addHandler(file_handler)
    
    # 添加控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    crash_logger.addHandler(console_handler)
    
    return crash_logger


def save_crash_info(group_name, crash_type, crash_info, additional_info=None):
    """
    保存崩溃信息到文件
    
    @param {str} group_name - 监控组名称
    @param {str} crash_type - 崩溃类型(exception, signal, resource_limit, unknown)
    @param {str} crash_info - 崩溃详细信息
    @param {dict} additional_info - 附加信息
    """
    project_root = utils.get_project_root()
    crash_dir = os.path.join(project_root, 'logs', group_name, 'crashes')
    os.makedirs(crash_dir, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    crash_file = os.path.join(crash_dir, f"crash_{timestamp}_{crash_type}.json")
    
    # 获取系统信息
    system_info = {
        "platform": sys.platform,
        "python_version": sys.version,
        "pid": os.getpid(),
        "process_name": psutil.Process().name(),
        "working_directory": os.getcwd(),
        "timestamp": datetime.datetime.now().isoformat(),
        "memory_usage": get_memory_usage(),
        "cpu_usage": get_cpu_usage()
    }
    
    # 合并附加信息
    if additional_info is None:
        additional_info = {}
    
    crash_data = {
        "crash_type": crash_type,
        "crash_info": crash_info,
        "system_info": system_info,
        "additional_info": additional_info
    }
    
    # 保存崩溃信息
    with open(crash_file, 'w', encoding='utf-8') as f:
        json.dump(crash_data, f, ensure_ascii=False, indent=2)
    
    # 记录到崩溃日志
    crash_logger = logging.getLogger(f"{group_name}_crash")
    crash_logger.error(f"程序崩溃: 类型={crash_type}, 信息={crash_info}")
    
    # 在最后活动文件中标记崩溃
    save_last_activity(group_name, "crashed", crash_type)


def get_memory_usage():
    """
    获取当前进程的内存使用情况
    
    @returns {dict} 内存使用信息
    """
    try:
        process = psutil.Process()
        memory_info = process.memory_info()
        return {
            "rss": memory_info.rss,  # 物理内存
            "vms": memory_info.vms,  # 虚拟内存
            "shared": getattr(memory_info, 'shared', 0),  # 共享内存
            "percent": process.memory_percent(),  # 内存使用百分比
            "readable": {
                "rss": f"{memory_info.rss / (1024*1024):.2f} MB",
                "vms": f"{memory_info.vms / (1024*1024):.2f} MB"
            }
        }
    except Exception as e:
        return {"error": str(e)}


def get_cpu_usage():
    """
    获取当前进程的CPU使用情况
    
    @returns {dict} CPU使用信息
    """
    try:
        process = psutil.Process()
        return {
            "percent": process.cpu_percent(interval=0.1),  # CPU使用百分比
            "threads": len(process.threads()),  # 线程数量
            "user_time": process.cpu_times().user,  # 用户态CPU时间
            "system_time": process.cpu_times().system,  # 系统态CPU时间
            "affinity": len(process.cpu_affinity()) if hasattr(process, 'cpu_affinity') else None  # CPU亲和性
        }
    except Exception as e:
        return {"error": str(e)}


def save_last_activity(group_name, activity_type, description=None):
    """
    保存最后活动信息
    
    @param {str} group_name - 监控组名称
    @param {str} activity_type - 活动类型(heartbeat, crashed, signal, shutdown)
    @param {str} description - 活动描述
    """
    project_root = utils.get_project_root()
    data_dir = os.path.join(project_root, 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    activity_file = os.path.join(data_dir, f"last_activity_{group_name}.json")
    
    activity_data = {
        "timestamp": datetime.datetime.now().isoformat(),
        "type": activity_type,
        "description": description,
        "pid": os.getpid()
    }
    
    with open(activity_file, 'w', encoding='utf-8') as f:
        json.dump(activity_data, f, ensure_ascii=False, indent=2)


def setup_excepthook(group_name):
    """
    设置全局未捕获异常处理器
    
    @param {str} group_name - 监控组名称
    """
    original_excepthook = sys.excepthook
    
    def custom_excepthook(exc_type, exc_value, exc_traceback):
        # 格式化异常信息
        exception_str = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        
        # 保存崩溃信息
        save_crash_info(
            group_name, 
            "exception", 
            str(exc_value),
            {
                "exception_type": exc_type.__name__,
                "traceback": exception_str
            }
        )
        
        # 记录到崩溃日志
        crash_logger = logging.getLogger(f"{group_name}_crash")
        crash_logger.critical(f"未捕获异常: {exc_type.__name__}: {exc_value}\n{exception_str}")
        
        # 调用原始的excepthook
        original_excepthook(exc_type, exc_value, exc_traceback)
    
    sys.excepthook = custom_excepthook


def setup_signal_handlers(group_name):
    """
    设置详细的信号处理器
    
    @param {str} group_name - 监控组名称
    """
    crash_logger = logging.getLogger(f"{group_name}_crash")
    
    # 定义信号处理函数
    def signal_handler(sig, frame):
        signal_name = signal.Signals(sig).name
        crash_logger.warning(f"收到信号: {signal_name} ({sig})")
        
        if sig in [signal.SIGINT, signal.SIGTERM]:
            save_crash_info(
                group_name,
                "signal",
                f"收到终止信号: {signal_name} ({sig})",
                {"stack_trace": ''.join(traceback.format_stack(frame))}
            )
            
            # 在最后活动文件中标记信号
            save_last_activity(group_name, "signal", signal_name)
            
            # 正常退出
            sys.exit(0)
        elif sig == signal.SIGPIPE:
            # 特殊处理SIGPIPE信号（Broken pipe），记录但不终止程序
            save_crash_info(
                group_name,
                "signal",
                f"收到管道破裂信号: {signal_name} ({sig})",
                {"stack_trace": ''.join(traceback.format_stack(frame))}
            )
            save_last_activity(group_name, "signal", signal_name)
            crash_logger.warning(f"收到管道破裂信号(SIGPIPE)，程序将继续运行")
        else:
            # 记录其他信号但不退出
            save_crash_info(
                group_name,
                "signal",
                f"收到信号: {signal_name} ({sig})",
                {"stack_trace": ''.join(traceback.format_stack(frame))}
            )
    
    # 注册信号处理器
    for sig in [signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGPIPE]:
        try:
            signal.signal(sig, signal_handler)
        except (AttributeError, ValueError):
            # 某些信号在特定平台不可用
            pass


def start_heartbeat(group_name, interval=10):
    """
    启动心跳监控线程
    
    @param {str} group_name - 监控组名称
    @param {int} interval - 心跳间隔(秒)
    """
    def heartbeat_thread():
        crash_logger = logging.getLogger(f"{group_name}_crash")
        crash_logger.info(f"心跳监控线程已启动，间隔 {interval} 秒")
        
        while True:
            try:
                # 记录心跳
                save_last_activity(group_name, "heartbeat")
                
                # 记录资源使用情况
                memory_usage = get_memory_usage()
                cpu_usage = get_cpu_usage()
                
                # 当资源使用超过阈值时记录警告
                if memory_usage.get('percent', 0) > 80:
                    crash_logger.warning(f"内存使用率过高: {memory_usage.get('percent')}%")
                
                if cpu_usage.get('percent', 0) > 80:
                    crash_logger.warning(f"CPU使用率过高: {cpu_usage.get('percent')}%")
                
                # 睡眠到下一个心跳周期
                time.sleep(interval)
            except Exception as e:
                crash_logger.error(f"心跳线程异常: {str(e)}")
                time.sleep(interval)  # 即使出错也保持周期
    
    # 创建心跳线程
    heartbeat_t = threading.Thread(target=heartbeat_thread, daemon=False, name=f"heartbeat-{group_name}")
    heartbeat_t.start()
    
    return heartbeat_t


def setup_exit_handler(group_name):
    """
    设置程序退出处理器
    
    @param {str} group_name - 监控组名称
    """
    crash_logger = logging.getLogger(f"{group_name}_crash")
    
    def exit_handler():
        """程序退出时执行的处理函数"""
        crash_logger.info("程序正常退出")
        save_last_activity(group_name, "shutdown", "程序正常退出")
    
    # 注册退出处理器
    atexit.register(exit_handler)


def initialize(group_name):
    """
    初始化崩溃处理系统
    
    @param {str} group_name - 监控组名称
    """
    # 设置崩溃日志
    crash_logger = setup_crash_logging(group_name)
    crash_logger.info(f"崩溃处理系统已初始化: {group_name}")
    
    # 设置异常钩子
    setup_excepthook(group_name)
    
    # 设置信号处理器
    setup_signal_handlers(group_name)
    
    # 设置退出处理器
    setup_exit_handler(group_name)
    
    # 启动心跳监控线程
    heartbeat_thread = start_heartbeat(group_name)
    
    # 记录初始化信息
    save_last_activity(group_name, "startup", "崩溃处理系统已初始化")
    
    return {
        "crash_logger": crash_logger,
        "heartbeat_thread": heartbeat_thread
    }


def check_last_crash(group_name):
    """
    检查最后一次崩溃信息
    
    @param {str} group_name - 监控组名称
    @returns {dict|None} 最后一次崩溃信息，如果没有崩溃则返回None
    """
    project_root = utils.get_project_root()
    activity_file = os.path.join(project_root, 'data', f"last_activity_{group_name}.json")
    
    if not os.path.exists(activity_file):
        return None
    
    try:
        with open(activity_file, 'r', encoding='utf-8') as f:
            activity_data = json.load(f)
        
        # 如果最后活动是崩溃，返回信息
        if activity_data.get('type') == 'crashed':
            crash_type = activity_data.get('description')
            timestamp = activity_data.get('timestamp')
            
            # 寻找对应的崩溃文件
            crash_dir = os.path.join(project_root, 'logs', group_name, 'crashes')
            if os.path.exists(crash_dir):
                crash_files = [f for f in os.listdir(crash_dir) if f.endswith('.json')]
                crash_files.sort(reverse=True)  # 按文件名降序排列，最新的在前面
                
                for crash_file in crash_files:
                    if crash_type in crash_file:
                        crash_path = os.path.join(crash_dir, crash_file)
                        with open(crash_path, 'r', encoding='utf-8') as f:
                            crash_data = json.load(f)
                        return crash_data
            
            # 如果没有找到详细的崩溃文件，返回简单信息
            return {
                "crash_type": crash_type,
                "timestamp": timestamp,
                "details": "未找到详细的崩溃信息文件"
            }
    except Exception as e:
        logging.error(f"读取最后崩溃信息失败: {str(e)}")
    
    return None


def format_last_crash_report(group_name):
    """
    格式化最后一次崩溃报告为可读字符串
    
    @param {str} group_name - 监控组名称
    @returns {str} 格式化的崩溃报告
    """
    crash_data = check_last_crash(group_name)
    
    if not crash_data:
        return "未发现崩溃记录"
    
    output = io.StringIO()
    
    output.write("=== 崩溃报告 ===\n\n")
    
    # 基本崩溃信息
    if isinstance(crash_data, dict) and 'crash_type' in crash_data:
        output.write(f"崩溃类型: {crash_data.get('crash_type')}\n")
        output.write(f"崩溃时间: {crash_data.get('timestamp', '未知')}\n")
        output.write(f"崩溃信息: {crash_data.get('crash_info', '未知')}\n\n")
        
        # 系统信息
        sys_info = crash_data.get('system_info', {})
        if sys_info:
            output.write("=== 系统信息 ===\n")
            output.write(f"平台: {sys_info.get('platform', '未知')}\n")
            output.write(f"Python版本: {sys_info.get('python_version', '未知')}\n")
            output.write(f"进程ID: {sys_info.get('pid', '未知')}\n")
            output.write(f"进程名称: {sys_info.get('process_name', '未知')}\n")
            output.write(f"工作目录: {sys_info.get('working_directory', '未知')}\n\n")
            
            # 资源使用情况
            mem_usage = sys_info.get('memory_usage', {})
            if isinstance(mem_usage, dict) and 'readable' in mem_usage:
                output.write("=== 内存使用 ===\n")
                output.write(f"物理内存: {mem_usage.get('readable', {}).get('rss', '未知')}\n")
                output.write(f"虚拟内存: {mem_usage.get('readable', {}).get('vms', '未知')}\n")
                output.write(f"内存使用率: {mem_usage.get('percent', '未知')}%\n\n")
            
            cpu_usage = sys_info.get('cpu_usage', {})
            if isinstance(cpu_usage, dict):
                output.write("=== CPU使用 ===\n")
                output.write(f"CPU使用率: {cpu_usage.get('percent', '未知')}%\n")
                output.write(f"线程数: {cpu_usage.get('threads', '未知')}\n\n")
        
        # 异常详情
        additional_info = crash_data.get('additional_info', {})
        if additional_info:
            if 'exception_type' in additional_info:
                output.write("=== 异常详情 ===\n")
                output.write(f"异常类型: {additional_info.get('exception_type', '未知')}\n\n")
            
            if 'traceback' in additional_info:
                output.write("=== 堆栈跟踪 ===\n")
                output.write(additional_info.get('traceback', '无堆栈信息')+ "\n\n")
            
            elif 'stack_trace' in additional_info:
                output.write("=== 堆栈跟踪 ===\n")
                output.write(additional_info.get('stack_trace', '无堆栈信息')+ "\n\n")
    else:
        # 简单模式
        output.write(f"崩溃信息: {str(crash_data)}\n")
    
    return output.getvalue() 