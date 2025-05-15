#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WAF监控 - 监控各监控进程的运行状态
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
from waf_monitor import watchdog


def signal_handler(sig, frame):
    """
    信号处理函数
    """
    print(f"[系统操作] 收到信号 {sig}，正在安全退出...")
    
    # 清理PID文件
    try:
        pid_file = os.path.join(project_root, 'data', 'watchdog.pid')
        if os.path.exists(pid_file):
            os.remove(pid_file)
            print(f"[系统维护] 已删除PID文件: {pid_file}")
    except Exception as e:
        print(f"[系统错误] 删除PID文件时出错: {str(e)}")
    
    sys.exit(0)


def main():
    """
    主函数
    """
    parser = argparse.ArgumentParser(description="WAF监控 - 监控各监控进程的运行状态")
    parser.add_argument('--check-interval', type=int, default=60,
                       help="检查间隔，单位秒，默认60秒")
    parser.add_argument('--max-restarts', type=int, default=5,
                       help="最大自动重启次数，默认5次")
    args = parser.parse_args()
    
    # 设置进程名称
    if setproctitle:
        setproctitle.setproctitle("waf-watchdog")
    
    # 设置当前PID
    current_pid = os.getpid()
    watchdog_pid_file = os.path.join(project_root, 'data', 'watchdog.pid')
    
    # 检查是否已有watchdog进程在运行
    if os.path.exists(watchdog_pid_file):
        try:
            with open(watchdog_pid_file, 'r') as f:
                old_pid = int(f.read().strip())
            
            # 检查是否真的有对应的进程在运行
            if utils.is_process_running(old_pid) and old_pid != current_pid:
                print(f"[系统警告] 另一个watchdog进程已经在运行 (PID: {old_pid})，当前进程将退出")
                return 1
            else:
                print(f"[系统维护] watchdog PID文件存在但进程不存在或已退出，将覆盖PID文件")
        except Exception as e:
            print(f"[系统错误] 读取watchdog PID文件时出错: {str(e)}，将创建新PID文件")
    
    # 写入当前PID
    try:
        with open(watchdog_pid_file, 'w') as f:
            f.write(str(current_pid))
        print(f"[系统初始化] 已创建watchdog PID文件，PID: {current_pid}")
    except Exception as e:
        print(f"[系统错误] 创建watchdog PID文件时出错: {str(e)}")
        return 1
    
    # 设置信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 加载配置
        config = utils.load_global_config()
        
        # 使用命令行参数覆盖配置
        if args.check_interval:
            config['watchdog_check_interval'] = args.check_interval
        if args.max_restarts:
            config['watchdog_max_restarts'] = args.max_restarts
        
        # 获取检查间隔时间
        check_interval = config.get('watchdog_check_interval', 60)
        
        print(f"[系统初始化] watchdog守护进程已启动，PID: {current_pid}，检查间隔: {check_interval}秒")
        
        # 创建并启动监控器
        dog = watchdog.create_watchdog(config)
        
        # 启动主循环并持续运行
        print(f"[系统初始化] 开始主循环监控，每 {check_interval} 秒检查一次进程状态")
        dog.running = True
        
        while True:
            try:
                # 定期检查PID文件是否存在，如果不存在则重新创建
                if not os.path.exists(watchdog_pid_file):
                    print(f"[系统维护] watchdog PID文件不存在，正在重新创建...")
                    with open(watchdog_pid_file, 'w') as f:
                        f.write(str(current_pid))
                    print(f"[系统维护] 已重新创建watchdog PID文件，PID: {current_pid}")
                
                # 执行一次检查循环
                dog.check_all_processes()
                
                # 等待下一次检查
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                print("[系统操作] 收到中断信号，正在退出...")
                break
                
            except Exception as e:
                print(f"[系统错误] 监控循环发生异常: {str(e)}")
                # 休眠一段时间后继续
                time.sleep(min(check_interval, 10))
    
    except KeyboardInterrupt:
        print("[系统操作] 收到中断信号，正在退出...")
    
    except Exception as e:
        print(f"[系统错误] 监控器运行出错: {str(e)}")
        # 异常情况下也清理PID文件
        try:
            if os.path.exists(watchdog_pid_file) and os.getpid() == current_pid:
                os.remove(watchdog_pid_file)
                print(f"[系统维护] 错误退出时已清理watchdog PID文件: {watchdog_pid_file}")
        except Exception as e:
            print(f"[系统错误] 清理watchdog PID文件时出错: {str(e)}")
        return 1
    
    # 删除PID文件
    try:
        if os.path.exists(watchdog_pid_file) and os.getpid() == current_pid:
            os.remove(watchdog_pid_file)
            print("[系统维护] 已删除watchdog PID文件")
    except Exception as e:
        print(f"[系统错误] 删除watchdog PID文件时出错: {str(e)}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 