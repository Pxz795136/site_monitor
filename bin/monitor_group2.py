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
    
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 创建并启动监控器
        url_monitor = monitor.create_monitor(GROUP_NAME)
        url_monitor.start()
        
        # 保持主进程运行
        print(f"{GROUP_NAME} 监控已启动，进程ID: {current_pid}, 按Ctrl+C退出...")
        while True:
            # 定期检查PID文件是否存在，如果不存在则重新创建
            if not os.path.exists(pid_file):
                print(f"PID文件不存在，正在重新创建...")
                with open(pid_file, 'w') as f:
                    f.write(str(current_pid))
                print(f"已重新创建PID文件，PID: {current_pid}")
            time.sleep(10)
    
    except KeyboardInterrupt:
        print("收到中断信号，正在退出...")
    
    except Exception as e:
        print(f"监控器运行出错: {str(e)}")
        # 异常情况下也清理PID文件
        try:
            if os.path.exists(pid_file) and os.getpid() == current_pid:
                os.remove(pid_file)
                print(f"错误退出时已清理PID文件: {pid_file}")
        except Exception as e:
            print(f"清理PID文件时出错: {str(e)}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 