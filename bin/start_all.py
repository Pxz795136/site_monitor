#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WAF监控 - 启动所有监控组
"""

import os
import sys
import subprocess
import time
import json
import psutil
import argparse
import signal

# 添加项目根目录到Python路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

from waf_monitor import utils


def setup_logging(log_file=None):
    """
    设置日志记录
    
    @param {str} log_file - 日志文件路径
    """
    import logging
    
    # 确保日志目录存在
    logs_dir = os.path.join(project_root, 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    # 如果没有指定日志文件，使用默认路径
    if log_file is None:
        # 创建一个启动脚本专用的目录
        daemon_logs_dir = os.path.join(logs_dir, 'daemon')
        os.makedirs(daemon_logs_dir, exist_ok=True)
        log_file = os.path.join(daemon_logs_dir, 'startup.log')
    
    # 配置根日志记录器
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # 创建文件处理器
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 创建日志格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器到日志记录器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def daemonize():
    """
    创建守护进程 - 统一模式，适用于所有平台，包括Linux和MacOS
    
    此方法确保进程能够在SSH会话断开后继续运行
    """
    # 添加SIGHUP信号处理器，防止SSH断开导致进程终止
    def handle_sighup(sig, frame):
        # 忽略SIGHUP信号
        print("收到SIGHUP信号(SSH断开)，忽略并继续运行")
    
    try:
        # 注册SIGHUP信号处理器，在Linux上防止SSH断开时终止进程
        signal.signal(signal.SIGHUP, handle_sighup)
    except (AttributeError, ValueError):
        # 某些平台可能不支持SIGHUP
        print("注意: 无法注册SIGHUP处理器，SSH断开可能会影响程序运行")
    
    print("创建后台进程...")
    
    # 确保日志目录存在
    logs_dir = os.path.join(project_root, 'logs')
    daemon_logs_dir = os.path.join(logs_dir, 'daemon')
    os.makedirs(daemon_logs_dir, exist_ok=True)
    
    # 准备日志文件
    daemon_log = os.path.join(daemon_logs_dir, 'daemon.log')
    daemon_err = os.path.join(daemon_logs_dir, 'daemon_error.log')
    
    # 在所有平台上使用统一的方式创建子进程
    args = [sys.executable, os.path.abspath(__file__), '--no-daemon',
            f'--log-file={daemon_log}']
    
    # 确保data目录存在，用于存储PID文件
    data_dir = os.path.join(project_root, 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    pid_file = os.path.join(data_dir, 'daemon.pid')
    
    # 打开日志文件
    out_log = open(daemon_log, 'w')
    err_log = open(daemon_err, 'w')
    
    try:
        # 创建子进程，确保完全脱离终端
        process = subprocess.Popen(
            args,
            stdout=out_log,
            stderr=err_log,
            stdin=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True  # 创建新会话，确保进程不受终端影响
        )
        
        # 等待短暂时间确认进程启动
        time.sleep(2)
        
        if utils.is_process_running(process.pid):
            print(f"\033[32m[✓] 守护进程创建成功!\033[0m PID: {process.pid}")
            print(f"\033[32m[✓] 启动日志将记录到: {daemon_log}\033[0m")
            print("\033[32m[✓] 可以使用 'python3 status.py' 查看监控状态\033[0m")
            
            # 写入PID文件
            with open(pid_file, 'w') as f:
                f.write(str(process.pid) + '\n')
                
            # 父进程退出，允许子进程继续在后台运行
            sys.exit(0)
        else:
            print("\033[31m[✗] 守护进程创建失败!\033[0m 请检查日志获取详细信息")
            print(f"\033[31m[✗] 错误日志: {daemon_err}\033[0m")
            sys.exit(1)
            
    except Exception as e:
        print(f"\033[31m[✗] 创建守护进程时出错: {str(e)}\033[0m")
        sys.exit(1)
    finally:
        # 关闭文件句柄
        out_log.close()
        err_log.close()


def update_watchdog_status(group_name, pid):
    """
    更新监控进程状态
    
    @param {str} group_name - 组名称
    @param {int} pid - 进程ID
    """
    watchdog_json_path = os.path.join(project_root, 'data', 'watchdog.json')
    watchdog_data = {}
    
    # 尝试读取现有状态
    if os.path.exists(watchdog_json_path):
        try:
            with open(watchdog_json_path, 'r', encoding='utf-8') as f:
                watchdog_data = json.load(f)
        except Exception as e:
            print(f"读取watchdog状态文件时出错: {str(e)}")
    
    # 更新或创建组的状态
    from datetime import datetime
    now = datetime.now().isoformat()
    
    if group_name in watchdog_data:
        watchdog_data[group_name]['pid'] = pid
        watchdog_data[group_name]['status'] = "运行中"
        watchdog_data[group_name]['restart_count'] = 0  # 重置重启计数
        watchdog_data[group_name]['last_check_time'] = now
        watchdog_data[group_name]['last_start_time'] = now
    else:
        watchdog_data[group_name] = {
            'group_name': group_name,
            'pid': pid,
            'status': "运行中",
            'restart_count': 0,
            'last_check_time': now,
            'last_start_time': now
        }
    
    # 保存更新后的状态
    try:
        with open(watchdog_json_path, 'w', encoding='utf-8') as f:
            json.dump(watchdog_data, f, ensure_ascii=False, indent=2)
        print(f"已更新 {group_name} 的监控状态")
    except Exception as e:
        print(f"保存watchdog状态文件时出错: {str(e)}")


def reset_all_restart_counts():
    """
    重置所有组的重启计数
    """
    watchdog_json_path = os.path.join(project_root, 'data', 'watchdog.json')
    if not os.path.exists(watchdog_json_path):
        return
    
    try:
        # 读取当前状态
        with open(watchdog_json_path, 'r', encoding='utf-8') as f:
            watchdog_data = json.load(f)
        
        # 修改所有组的重启计数和状态
        updated = False
        for group in watchdog_data:
            old_count = watchdog_data[group].get('restart_count', 0)
            old_status = watchdog_data[group].get('status', '未知')
            
            if old_count > 0 or old_status == "已停止 - 超过最大重启次数":
                watchdog_data[group]['restart_count'] = 0
                if old_status == "已停止 - 超过最大重启次数":
                    watchdog_data[group]['status'] = "已停止"
                updated = True
                print(f"已重置 {group} 状态: 重启计数 {old_count} -> 0")
        
        # 保存更新后的状态
        if updated:
            with open(watchdog_json_path, 'w', encoding='utf-8') as f:
                json.dump(watchdog_data, f, ensure_ascii=False, indent=2)
            print("已保存更新后的watchdog状态")
    
    except Exception as e:
        print(f"重置重启计数时出错: {str(e)}")


def start_group(group_name):
    """
    启动指定组的监控
    
    @param {str} group_name - 组名称
    @returns {bool} 启动是否成功
    """
    print(f"正在启动 {group_name} 监控...")
    
    # 检查PID文件
    pid_file = os.path.join(project_root, 'data', f"{group_name}.pid")
    if os.path.exists(pid_file):
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # 更严格地检查进程是否真的在运行
            if pid and utils.is_process_running(pid):
                # 进一步验证这确实是我们的监控进程
                try:
                    process = psutil.Process(pid)
                    cmdline = process.cmdline()
                    
                    # 检查命令行是否包含当前组的监控脚本
                    if any(f"monitor_{group_name}.py" in cmd for cmd in cmdline):
                        print(f"{group_name} 监控已经在运行，PID: {pid}")
                        # 更新watchdog状态
                        update_watchdog_status(group_name, pid)
                        return True
                    else:
                        print(f"发现PID文件但进程({pid})不是监控进程，将删除PID文件并重新启动")
                        os.remove(pid_file)
                except Exception as e:
                    print(f"验证进程时出错: {str(e)}，将删除PID文件并重新启动")
                    os.remove(pid_file)
            else:
                # PID文件存在但进程不存在，删除PID文件
                print(f"PID文件指向的进程({pid})不存在，将删除过期的PID文件")
                os.remove(pid_file)
        except Exception as e:
            print(f"读取PID文件出错: {str(e)}，将删除PID文件")
            try:
                os.remove(pid_file)
            except:
                pass
    
    # 检查是否因超过最大重启次数而停止
    watchdog_status_path = os.path.join(project_root, 'data', 'watchdog.json')
    if os.path.exists(watchdog_status_path):
        try:
            with open(watchdog_status_path, 'r', encoding='utf-8') as f:
                watchdog_data = json.load(f)
                
            # 如果该组存在且状态显示已超过最大重启次数
            if (group_name in watchdog_data and 
                'status' in watchdog_data[group_name] and 
                'restart_count' in watchdog_data[group_name] and
                watchdog_data[group_name]['status'] == "已停止 - 超过最大重启次数"):
                
                print(f"{group_name} 监控之前因超过最大重启次数而停止，正在重置状态...")
                # 不需要额外处理，下面的update_watchdog_status会重置状态
        except Exception as e:
            print(f"读取watchdog状态文件时出错: {str(e)}")
    
    # 组装启动命令
    python_executable = sys.executable
    script_path = os.path.join(script_dir, f"monitor_{group_name}.py")
    
    try:
        # 启动进程，确保完全独立并能在SSH断开后继续运行
        logs_dir = os.path.join(project_root, 'logs', group_name)
        os.makedirs(logs_dir, exist_ok=True)
        log_file = os.path.join(logs_dir, "startup.log")
        
        # 创建启动脚本包装器，确保子进程能忽略SIGHUP信号
        wrapper_script = os.path.join(project_root, 'data', f"start_{group_name}_wrapper.py")
        with open(wrapper_script, 'w') as f:
            f.write(f"""#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 启动包装脚本 - 自动生成
import os
import sys
import signal

# 忽略SIGHUP信号，允许在SSH断开后继续运行
try:
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
except (AttributeError, ValueError):
    pass

# 启动原始脚本
os.execv("{python_executable}", ["{python_executable}", "{script_path}"])
""")
        
        # 设置包装脚本可执行权限
        os.chmod(wrapper_script, 0o755)
        
        with open(log_file, 'w') as log_f:
            process = subprocess.Popen(
                [python_executable, wrapper_script],
                stdout=log_f,
                stderr=log_f,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                cwd=project_root,
                close_fds=True  # 确保关闭所有继承的文件描述符
            )
        
        # 等待片刻确认进程启动
        time.sleep(2)
        
        # 检查进程是否成功启动
        new_pid = utils.load_pid(group_name)
        if new_pid and utils.is_process_running(new_pid):
            print(f"{group_name} 监控已成功启动，PID: {new_pid}")
            # 更新watchdog状态
            update_watchdog_status(group_name, new_pid)
            return True
        else:
            print(f"{group_name} 监控启动失败")
            return False
            
    except Exception as e:
        print(f"启动 {group_name} 时出错: {str(e)}")
        return False


def start_watchdog():
    """
    启动watchdog进程
    
    @returns {bool} 启动是否成功
    """
    print("正在启动监控进程守护程序...")
    watchdog_script = os.path.join(script_dir, 'watchdog.py')
    
    try:
        # 使用专用的日志文件
        logs_dir = os.path.join(project_root, 'logs', 'watchdog')
        os.makedirs(logs_dir, exist_ok=True)
        log_file = os.path.join(logs_dir, 'startup.log')
        
        # 创建启动脚本包装器，确保子进程能忽略SIGHUP信号
        wrapper_script = os.path.join(project_root, 'data', "start_watchdog_wrapper.py")
        with open(wrapper_script, 'w') as f:
            f.write(f"""#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 启动包装脚本 - 自动生成
import os
import sys
import signal

# 忽略SIGHUP信号，允许在SSH断开后继续运行
try:
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
except (AttributeError, ValueError):
    pass

# 启动原始脚本
os.execv("{sys.executable}", ["{sys.executable}", "{watchdog_script}"])
""")
        
        # 设置包装脚本可执行权限
        os.chmod(wrapper_script, 0o755)
        
        with open(log_file, 'w') as log_f:
            watchdog_process = subprocess.Popen(
                [sys.executable, wrapper_script],
                stdout=log_f,
                stderr=log_f,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                cwd=project_root,
                close_fds=True  # 确保关闭所有继承的文件描述符
            )
        
        # 等待几秒钟确认watchdog进程已成功启动
        time.sleep(5)
        
        # 验证watchdog进程是否真的在运行
        if utils.is_process_running(watchdog_process.pid):
            print(f"Watchdog进程已成功启动，PID: {watchdog_process.pid}")
            return True
        else:
            print(f"警告: Watchdog进程似乎未能成功启动")
            return False
    except Exception as e:
        print(f"启动Watchdog进程时出错: {str(e)}")
        return False


def main():
    """
    主函数，启动所有监控组
    """
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="WAF监控 - 启动所有监控组")
    parser.add_argument('--no-daemon', action='store_true', 
                        help='不以守护进程方式运行（默认以守护进程方式运行）')
    parser.add_argument('--log-file', 
                        help='日志文件路径（仅在非守护进程模式下有效）')
    args = parser.parse_args()
    
    # 如果以守护进程方式运行，执行脱离终端的过程
    if not args.no_daemon:
        print("以守护进程方式启动...")
        daemonize()
    else:
        # 在非守护进程模式下也注册SIGHUP处理器，防止SSH断开导致进程终止
        def handle_sighup(sig, frame):
            print("收到SIGHUP信号(SSH断开)，忽略并继续运行")
        
        try:
            signal.signal(signal.SIGHUP, handle_sighup)
        except (AttributeError, ValueError):
            print("注意: 无法注册SIGHUP处理器，SSH断开可能会影响程序运行")
        
        # 在非守护进程模式下设置日志
        setup_logging(args.log_file)
    
    # 从全局配置获取监控组列表
    try:
        global_config = utils.load_global_config()
        groups = global_config.get('monitor_groups', ['group1', 'group2', 'group3', 'group4', 'group5', 'group6'])
    except Exception as e:
        print(f"加载配置失败: {str(e)}")
        groups = ['group1', 'group2', 'group3', 'group4', 'group5', 'group6']
    
    # 重置所有组的重启计数（自动修复）
    print("执行预检查：重置所有组的重启计数...")
    reset_all_restart_counts()
    
    # 首先启动各组监控，确保所有进程状态稳定
    success_count = 0
    for group in groups:
        try:
            if start_group(group):
                success_count += 1
        except Exception as e:
            print(f"启动 {group} 监控组时出现未预期的错误: {str(e)}")
    
    # 等待一段时间，确保所有进程都已经稳定运行
    wait_time = global_config.get('startup_wait_time', 15)
    print(f"等待所有监控进程稳定运行...({wait_time}秒)")
    time.sleep(wait_time)
    
    # 最后才启动watchdog进程
    if not start_watchdog():
        print("警告: Watchdog进程启动失败，监控进程可能无法自动恢复")
    
    print(f"启动完成，共成功启动 {success_count}/{len(groups)} 个监控组")
    
    # 在守护进程模式下，进程会继续运行在后台
    # 在非守护进程模式下，进程会在此退出
    if args.no_daemon:
        # 如果用户使用Ctrl+C结束程序，优雅关闭
        def handle_interrupt(sig, frame):
            print("\n收到中断信号，正在优雅关闭...")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, handle_interrupt)
        signal.signal(signal.SIGTERM, handle_interrupt)
        
        print("\n程序正在前台运行中，按Ctrl+C可以退出...")
        
        # 保持主进程运行，直到用户中断
        while True:
            try:
                time.sleep(60)  # 每分钟检查一次
                # 可以在这里添加其他周期性任务
            except KeyboardInterrupt:
                print("\n收到用户中断，正在退出...")
                break
            except Exception as e:
                print(f"主循环中发生错误: {str(e)}")
        
        if success_count < len(groups):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main()) 