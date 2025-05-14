#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WAF监控 - 第二组监控脚本
"""

import os
import sys
import time
import signal
import argparse

# 添加项目根目录到Python路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

try:
    import setproctitle
except ImportError:
    setproctitle = None

from waf_monitor import utils
from waf_monitor import monitor
from waf_monitor import crash_handler

GROUP_NAME = 'group2'


def signal_handler(sig, frame):
    """
    信号处理函数
    """
    print(f"收到信号 {sig}，正在退出...")
    
    # 清理PID文件
    try:
        pid_file = os.path.join(project_root, 'data', f"{GROUP_NAME}.pid")
        if os.path.exists(pid_file):
            os.remove(pid_file)
            print(f"已删除PID文件: {pid_file}")
    except Exception as e:
        print(f"删除PID文件时出错: {str(e)}")
    
    sys.exit(0)


def main():
    """
    主函数
    """
    # 设置进程名称
    if setproctitle:
        setproctitle.setproctitle(f"waf-monitor-{GROUP_NAME}")
    
    # 先检查是否有已存在的同名进程
    import psutil
    current_pid = os.getpid()
    pid_file = os.path.join(project_root, 'data', f"{GROUP_NAME}.pid")
    
    # 检查PID文件是否存在
    if os.path.exists(pid_file):
        try:
            with open(pid_file, 'r') as f:
                old_pid = int(f.read().strip())
            
            # 检查是否有其他进程在运行
            if utils.is_process_running(old_pid) and old_pid != current_pid:
                print(f"警告: 另一个 {GROUP_NAME} 监控进程正在运行 (PID: {old_pid})，当前进程将退出")
                return 1
            else:
                print(f"PID文件存在但进程不存在或已退出，将覆盖PID文件")
        except Exception as e:
            print(f"读取PID文件时出错: {str(e)}，将创建新PID文件")
    
    # 保存进程ID并设置退出时自动清理
    try:
        # 确保数据目录存在
        data_dir = os.path.join(project_root, 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        # 直接创建PID文件，不通过utils模块
        with open(pid_file, 'w') as f:
            f.write(str(current_pid))
        print(f"已创建PID文件，PID: {current_pid}")
        
        # 再次验证PID文件是否成功创建
        if os.path.exists(pid_file):
            with open(pid_file, 'r') as f:
                saved_pid = f.read().strip()
                if saved_pid != str(current_pid):
                    print(f"警告: PID文件内容 ({saved_pid}) 与当前进程PID ({current_pid}) 不匹配")
        else:
            print(f"警告: PID文件创建失败")
        
        # 注册进程退出钩子，确保在任何情况下都能清理PID文件
        import atexit
        def cleanup_pid_file():
            try:
                if os.path.exists(pid_file) and os.getpid() == current_pid:
                    os.remove(pid_file)
                    print(f"进程退出前已清理PID文件: {pid_file}")
            except Exception as e:
                print(f"清理PID文件时出错: {str(e)}")
        atexit.register(cleanup_pid_file)
    except Exception as e:
        print(f"创建PID文件时出错: {str(e)}")
    
    # 捕获所有未处理的异常
    def global_exception_handler(exctype, value, traceback_obj):
        print(f"捕获到未处理的异常: {exctype.__name__}: {value}")
        import traceback
        traceback_str = ''.join(traceback.format_exception(exctype, value, traceback_obj))
        print(f"堆栈跟踪:\n{traceback_str}")
        # 清理PID文件
        try:
            if os.path.exists(pid_file) and os.getpid() == current_pid:
                os.remove(pid_file)
                print(f"异常处理时已清理PID文件: {pid_file}")
        except Exception as e:
            print(f"清理PID文件时出错: {str(e)}")
        # 调用原始异常处理器
        sys.__excepthook__(exctype, value, traceback_obj)
    
    # 设置全局异常处理器
    sys.excepthook = global_exception_handler
    
    # 初始化崩溃处理系统
    try:
        crash_handler_context = crash_handler.initialize(GROUP_NAME)
        crash_logger = crash_handler_context['crash_logger']
        crash_logger.info(f"{GROUP_NAME} 监控启动，PID: {current_pid}")
    except Exception as e:
        print(f"初始化崩溃处理系统失败: {str(e)}")
        # 创建基本的日志记录器
        import logging
        crash_logger = logging.getLogger(f"{GROUP_NAME}_crash")
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        crash_logger.addHandler(handler)
        crash_logger.setLevel(logging.INFO)
        crash_logger.warning(f"使用备用日志系统: {str(e)}")
    
    # 检查上次崩溃
    try:
        last_crash = crash_handler.check_last_crash(GROUP_NAME)
        if last_crash:
            crash_type = last_crash.get('crash_type', '未知')
            crash_time = last_crash.get('timestamp', '未知时间')
            crash_info = last_crash.get('crash_info', '未知原因')
            crash_logger.warning(f"检测到上次程序异常退出: 类型={crash_type}, 时间={crash_time}, 原因={crash_info}")
            print(f"\n警告: 检测到上次程序异常退出!")
            print(f"类型: {crash_type}")
            print(f"时间: {crash_time}")
            print(f"原因: {crash_info}")
            print(f"使用命令查看详细信息: python bin/crash_report.py {GROUP_NAME} --last\n")
    except Exception as e:
        crash_logger.error(f"检查上次崩溃时出错: {str(e)}")
    
    # 注册信号处理
    try:
        # 注册基本信号处理
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # 特殊处理SIGPIPE信号
        def handle_sigpipe(sig, frame):
            crash_logger.warning(f"收到SIGPIPE信号，忽略并继续运行")
            # 不退出，让程序继续运行
        
        try:
            signal.signal(signal.SIGPIPE, handle_sigpipe)
            crash_logger.info("已注册SIGPIPE处理器")
        except (AttributeError, ValueError) as e:
            crash_logger.warning(f"无法注册SIGPIPE处理器: {str(e)}")
    except Exception as e:
        crash_logger.error(f"设置信号处理器时出错: {str(e)}")
    
    url_monitor = None
    try:
        # 创建并启动监控器
        url_monitor = monitor.create_monitor(GROUP_NAME)
        url_monitor.start()
        
        # 保持主进程运行
        print(f"{GROUP_NAME} 监控已启动，进程ID: {current_pid}, 按Ctrl+C退出...")
        restart_count = 0
        max_restarts = 10  # 最大重启次数
        restart_threshold = 300  # 重启阈值(秒)
        last_restart_time = 0
        
        while True:
            try:
                # 定期检查PID文件是否存在，如果不存在则重新创建
                if not os.path.exists(pid_file):
                    crash_logger.warning(f"PID文件不存在，正在重新创建...")
                    with open(pid_file, 'w') as f:
                        f.write(str(current_pid))
                    crash_logger.info(f"已重新创建PID文件，PID: {current_pid}")
                
                # 检查监控线程是否还在运行
                if hasattr(url_monitor, '_monitor_thread') and not url_monitor._monitor_thread.is_alive():
                    # 计算重启频率
                    current_time = time.time()
                    elapsed = current_time - last_restart_time
                    
                    if last_restart_time > 0 and elapsed < restart_threshold:
                        restart_count += 1
                        if restart_count > max_restarts:
                            crash_logger.error(f"监控线程在{restart_threshold}秒内重启超过{max_restarts}次，退出程序")
                            raise RuntimeError(f"监控线程过于频繁重启 (已重启{restart_count}次)")
                        
                        # 计算退避时间
                        backoff = min(60, 2 ** (restart_count - 1))
                        crash_logger.warning(f"监控线程频繁重启，等待{backoff}秒后再次尝试...")
                        time.sleep(backoff)
                    else:
                        # 如果距离上次重启时间足够长，重置计数器
                        if last_restart_time > 0 and elapsed >= restart_threshold:
                            restart_count = 0
                    
                    crash_logger.warning(f"检测到监控线程已退出，正在重新启动...(重启计数:{restart_count})")
                    print(f"检测到监控线程已退出，正在重新启动...(重启计数:{restart_count})")
                    # 记录本次重启时间
                    last_restart_time = current_time
                    # 重新启动监控线程
                    url_monitor.start()
                    crash_logger.info(f"监控线程已重新启动")
                    print(f"监控线程已重新启动")
                
                # 每10秒检查一次
                time.sleep(10)
            except Exception as e:
                crash_logger.error(f"主循环异常: {str(e)}")
                time.sleep(10)  # 出错时仍然保持循环
    
    except KeyboardInterrupt:
        print("收到中断信号，正在退出...")
        crash_logger.info("收到键盘中断信号，程序正常退出")
    
    except Exception as e:
        crash_logger.error(f"监控器运行出错: {str(e)}")
        # 记录详细的堆栈信息
        import traceback
        crash_logger.error(f"详细错误信息:\n{traceback.format_exc()}")
        print(f"监控器运行出错: {str(e)}")
        # 异常情况下也清理PID文件
        try:
            if os.path.exists(pid_file) and os.getpid() == current_pid:
                os.remove(pid_file)
                print(f"错误退出时已清理PID文件: {pid_file}")
        except Exception as e:
            print(f"清理PID文件时出错: {str(e)}")
        return 1
    
    finally:
        # 确保在所有情况下都尝试停止监控器
        if url_monitor is not None:
            try:
                url_monitor.stop()
                print("已停止监控器")
            except Exception as e:
                print(f"停止监控器时出错: {str(e)}")
        
        # 确保在所有情况下都尝试清理PID文件
        try:
            if os.path.exists(pid_file) and os.getpid() == current_pid:
                os.remove(pid_file)
                print(f"程序退出时已清理PID文件: {pid_file}")
        except Exception as e:
            print(f"清理PID文件时出错: {str(e)}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 