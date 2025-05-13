#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WAF监控 - 停止所有监控组
"""

import os
import sys
import signal
import time
import psutil  # 添加psutil库
import json  # 添加json库
from datetime import datetime
import subprocess

# 添加项目根目录到Python路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

from waf_monitor import utils


def stop_group(group_name):
    """
    停止指定组的监控
    
    @param {str} group_name - 组名称
    @returns {bool} 停止是否成功
    """
    print(f"正在停止 {group_name} 监控...")
    group_stopped = False
    found_process = False
    process_errors = []
    target_pids = []
    
    # 1. 先通过PID文件尝试停止
    pid = utils.load_pid(group_name)
    if pid:
        found_process = True
        print(f"从PID文件找到进程ID: {pid}")
        target_pids.append(pid)
        
        # PID文件无论如何都要删除，确保清理
        pid_file = os.path.join(project_root, 'data', f"{group_name}.pid")
        if os.path.exists(pid_file):
            try:
                os.remove(pid_file)
                print(f"已删除 {group_name} 的PID文件")
            except Exception as e:
                print(f"删除 {group_name} 的PID文件时出错: {str(e)}")
    else:
        print(f"未找到 {group_name} 的PID文件，将尝试通过进程名查找...")
    
    # 2. 查找所有Python进程，收集可能的目标进程
    try:
        # 遍历所有进程找到可能的监控进程
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # 如果进程PID在上面的列表中，跳过它，因为已经被标记为目标
                if proc.pid in target_pids:
                    continue
                
                # 获取进程名称和命令行
                proc_cmdline = ' '.join(proc.cmdline()) if proc.cmdline() else ''
                
                # 使用多种模式匹配可能的目标进程，提高成功率
                if any([
                    # 明确匹配该组的监控脚本名
                    f"monitor_{group_name}.py" in proc_cmdline,
                    # 进程名匹配
                    f"waf-monitor-{group_name}" in proc_cmdline,
                    # 命令行参数包含该组名
                    f"GROUP_NAME = '{group_name}'" in proc_cmdline or f'GROUP_NAME = "{group_name}"' in proc_cmdline,
                    # 宽松匹配：Python进程且命令行含有组名和"monitor"
                    ("python" in proc_cmdline or "python3" in proc_cmdline) and group_name in proc_cmdline and "monitor" in proc_cmdline 
                ]):
                    target_pids.append(proc.pid)
                    found_process = True
                    print(f"通过命令行找到 {group_name} 可能的监控进程，PID: {proc.pid}")
            
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                process_errors.append(f"检查进程时出错: {str(e)}")
                continue
    
    except Exception as e:
        print(f"搜索进程时出错: {str(e)}")
    
    # 3. 尝试终止所有找到的目标进程
    terminated_count = 0
    if target_pids:
        print(f"找到 {len(target_pids)} 个可能的 {group_name} 进程，PID列表: {target_pids}")
        
        for pid in target_pids:
            try:
                if utils.is_process_running(pid):
                    # 先尝试使用SIGTERM信号
                    print(f"向进程 {pid} 发送终止信号 (SIGTERM)")
                    os.kill(pid, signal.SIGTERM)
                    
                    # 等待进程退出
                    timeout = 5  # 最多等待5秒
                    for i in range(timeout):
                        if not utils.is_process_running(pid):
                            print(f"进程 {pid} 已成功停止")
                            terminated_count += 1
                            break
                        time.sleep(1)
                    
                    # 如果进程仍在运行，尝试使用SIGKILL信号强制终止
                    if utils.is_process_running(pid):
                        print(f"进程 {pid} 未响应SIGTERM信号，使用SIGKILL强制终止")
                        os.kill(pid, signal.SIGKILL)
                        time.sleep(1)
                        
                        if not utils.is_process_running(pid):
                            print(f"进程 {pid} 已被强制终止")
                            terminated_count += 1
                        else:
                            print(f"警告: 进程 {pid} 无法终止，可能需要手动干预")
                else:
                    print(f"进程 {pid} 已不存在，无需终止")
                    terminated_count += 1
            
            except Exception as e:
                print(f"终止进程 {pid} 时出错: {str(e)}")
    
    # 4. 使用macOS特定命令尝试查找和终止进程（最后的尝试）
    if found_process and terminated_count == 0:
        try:
            # 在macOS上使用pgrep和pkill尝试终止进程
            monitor_pattern = f"monitor_{group_name}|waf-monitor-{group_name}"
            
            # 尝试使用pgrep查找
            print(f"尝试使用macOS系统命令查找和终止 {group_name} 进程...")
            pgrep_result = subprocess.run(["pgrep", "-f", monitor_pattern], 
                                          stdout=subprocess.PIPE, 
                                          stderr=subprocess.PIPE,
                                          text=True)
            
            if pgrep_result.returncode == 0 and pgrep_result.stdout.strip():
                macos_pids = pgrep_result.stdout.strip().split('\n')
                print(f"使用pgrep找到可能的进程: {macos_pids}")
                
                # 尝试使用pkill终止这些进程
                pkill_result = subprocess.run(["pkill", "-f", monitor_pattern],
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE)
                
                if pkill_result.returncode == 0:
                    print(f"已使用pkill成功终止 {group_name} 进程")
                    terminated_count += 1
                else:
                    print(f"pkill命令执行失败，尝试强制终止...")
                    subprocess.run(["pkill", "-9", "-f", monitor_pattern])
                    print(f"已尝试使用pkill -9强制终止 {group_name} 进程")
        except Exception as e:
            print(f"使用系统命令终止进程时出错: {str(e)}")
    
    # 5. 更新watchdog.json中的状态
    try:
        watchdog_json_path = os.path.join(project_root, 'data', 'watchdog.json')
        if os.path.exists(watchdog_json_path):
            with open(watchdog_json_path, 'r', encoding='utf-8') as f:
                watchdog_data = json.load(f)
            
            # 如果该组存在，更新其状态
            if group_name in watchdog_data:
                # 记录旧状态
                old_status = watchdog_data[group_name].get('status', '未知')
                
                # 更新为已手动停止状态
                watchdog_data[group_name]['status'] = "已手动停止"
                watchdog_data[group_name]['pid'] = None
                watchdog_data[group_name]['need_alert'] = False  # 明确标记不需要告警
                
                # 重置重启计数
                if 'restart_count' in watchdog_data[group_name]:
                    old_count = watchdog_data[group_name]['restart_count']
                    if old_count > 0:
                        watchdog_data[group_name]['restart_count'] = 0
                        print(f"已重置 {group_name} 的重启计数: {old_count} -> 0")
                
                # 保存更新后的状态
                with open(watchdog_json_path, 'w', encoding='utf-8') as f:
                    json.dump(watchdog_data, f, ensure_ascii=False, indent=2)
                
                print(f"已更新 {group_name} 的状态: {old_status} -> 已手动停止")
            else:
                print(f"警告: {group_name} 在watchdog.json中不存在，创建新条目")
                # 创建新条目
                watchdog_data[group_name] = {
                    'group_name': group_name,
                    'pid': None,
                    'status': "已手动停止",
                    'restart_count': 0,
                    'last_check_time': datetime.now().isoformat(),
                    'last_start_time': datetime.now().isoformat(),
                    'was_restarted': False,
                    'need_alert': False
                }
                # 保存更新后的状态
                with open(watchdog_json_path, 'w', encoding='utf-8') as f:
                    json.dump(watchdog_data, f, ensure_ascii=False, indent=2)
                
                print(f"已为 {group_name} 创建新的状态记录")
    except Exception as e:
        print(f"更新 {group_name} 在watchdog.json中的状态时出错: {str(e)}")
    
    # 停止是否成功的判断
    if terminated_count > 0:
        print(f"成功停止了 {terminated_count} 个 {group_name} 进程")
        group_stopped = True
    elif found_process:
        print(f"警告: 找到了 {group_name} 进程但未能成功停止，可能需要手动干预")
        group_stopped = False
    else:
        print(f"未找到任何运行中的 {group_name} 监控进程")
        # 虽然没找到进程，但认为停止操作已完成
        group_stopped = True
    
    return group_stopped


def stop_watchdog():
    """
    停止监控守护进程
    
    @returns {bool} 停止是否成功
    """
    print("正在停止监控进程守护程序...")
    
    # 查找watchdog进程
    watchdog_pid_file = os.path.join(project_root, 'data', 'watchdog.pid')
    watchdog_stopped = False
    
    # 1. 先尝试通过PID文件停止
    try:
        if os.path.exists(watchdog_pid_file):
            with open(watchdog_pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # 检查进程是否存在
            if utils.is_process_running(pid):
                # 验证这确实是watchdog进程
                try:
                    process = psutil.Process(pid)
                    cmd_valid = False
                    
                    try:
                        cmdline = process.cmdline()
                        if any('watchdog.py' in cmd for cmd in cmdline):
                            cmd_valid = True
                    except:
                        # 无法获取命令行时，假定进程有效
                        cmd_valid = True
                    
                    if cmd_valid:
                        # 发送终止信号
                        print(f"向watchdog守护进程 (PID: {pid}) 发送终止信号...")
                        os.kill(pid, signal.SIGTERM)
                        
                        # 等待进程退出
                        for i in range(5):  # 最多等待5秒
                            if not utils.is_process_running(pid):
                                print("监控进程守护程序已停止")
                                watchdog_stopped = True
                                break
                            time.sleep(1)
                        
                        # 如果进程仍然存在，发送强制终止信号
                        if utils.is_process_running(pid):
                            print("watchdog进程未响应终止信号，强制终止...")
                            os.kill(pid, signal.SIGKILL)
                            time.sleep(1)
                            print("监控进程守护程序已强制停止")
                            watchdog_stopped = True
                    else:
                        print(f"PID文件指向的进程 (PID: {pid}) 不是watchdog进程，将删除PID文件")
                except Exception as e:
                    print(f"验证watchdog进程时出错: {str(e)}")
            else:
                print("监控进程守护程序未运行（PID文件已过期）")
            
            # 删除PID文件
            if os.path.exists(watchdog_pid_file):
                os.remove(watchdog_pid_file)
                print("已删除watchdog PID文件")
    except Exception as e:
        print(f"通过PID文件停止监控进程守护程序时出错: {str(e)}")
    
    # 2. 使用psutil查找所有可能的watchdog进程
    try:
        # 获取所有Python进程
        python_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # 只收集Python进程
                if proc.info['name'] in ['python', 'python3'] or (proc.info['cmdline'] and any(cmd.endswith(('python', 'python3')) for cmd in proc.info['cmdline'])):
                    python_processes.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # 在Python进程中查找watchdog相关进程
        watchdog_count = 0
        for proc in python_processes:
            try:
                cmd = ' '.join(proc.cmdline()) if proc.cmdline() else ''
                
                # 匹配任意标识watchdog的字符串
                if any(pattern in cmd for pattern in [
                    'watchdog.py',
                    'waf-watchdog'
                ]):
                    watchdog_count += 1
                    pid = proc.pid
                    print(f"找到watchdog进程，PID: {pid}")
                    
                    # 尝试终止进程
                    try:
                        proc.terminate()
                        print(f"已向watchdog进程 (PID: {pid}) 发送终止信号")
                        
                        # 等待进程退出
                        try:
                            proc.wait(timeout=5)
                            print(f"watchdog进程已停止 (PID: {pid})")
                            watchdog_stopped = True
                        except psutil.TimeoutExpired:
                            # 超时后强制终止
                            print(f"watchdog进程未响应终止信号，强制终止... (PID: {pid})")
                            proc.kill()
                            time.sleep(1)
                            print(f"watchdog进程已强制停止 (PID: {pid})")
                            watchdog_stopped = True
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        print(f"无法终止watchdog进程 (PID: {pid})，可能需要更高权限")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if watchdog_count > 0:
            print(f"共停止了 {watchdog_count} 个监控进程守护程序")
        elif not watchdog_stopped:
            print("未找到运行中的监控进程守护程序")
            
    except Exception as e:
        print(f"通过进程名称停止监控进程守护程序时出错: {str(e)}")
    
    return True


def main():
    """
    主函数，停止所有监控组
    """
    # 从全局配置获取监控组列表
    try:
        global_config = utils.load_global_config()
        groups = global_config.get('monitor_groups', ['group1', 'group2', 'group3', 'group4'])
    except Exception as e:
        print(f"加载配置失败: {str(e)}")
        groups = ['group1', 'group2', 'group3', 'group4']
    
    # 首先停止监控守护进程，避免它重启被停止的进程
    print("第1步：停止监控守护进程...")
    stop_watchdog()
    
    # 然后停止所有监控组
    print("第2步：停止所有监控组...")
    success_count = 0
    for group in groups:
        if stop_group(group):
            success_count += 1
    
    # 最后再次检查是否有漏网之鱼
    print("第3步：检查是否有残留进程...")
    try:
        # 再次检查watchdog进程
        stop_watchdog()
        
        # 检查是否有残留的监控进程
        for group in groups:
            stop_group(group)
            
        # 清理所有PID文件
        print("第4步：清理PID文件...")
        data_dir = os.path.join(project_root, 'data')
        for filename in os.listdir(data_dir):
            if filename.endswith('.pid'):
                pid_path = os.path.join(data_dir, filename)
                try:
                    os.remove(pid_path)
                    print(f"已删除PID文件: {filename}")
                except Exception as e:
                    print(f"删除PID文件 {filename} 时出错: {str(e)}")
                    
        # 重置watchdog.json中的重启计数器
        print("第5步：重置监控进程重启计数器...")
        watchdog_json_path = os.path.join(data_dir, 'watchdog.json')
        if os.path.exists(watchdog_json_path):
            try:
                # 读取现有状态
                with open(watchdog_json_path, 'r', encoding='utf-8') as f:
                    watchdog_data = json.load(f)
                
                # 重置所有组的重启计数
                updated = False
                for group in watchdog_data:
                    if 'restart_count' in watchdog_data[group]:
                        watchdog_data[group]['restart_count'] = 0
                        updated = True
                        print(f"已重置 {group} 的重启计数")
                
                # 保存更新后的状态
                if updated:
                    with open(watchdog_json_path, 'w', encoding='utf-8') as f:
                        json.dump(watchdog_data, f, ensure_ascii=False, indent=2)
                    print(f"已保存更新后的watchdog状态")
            except Exception as e:
                print(f"重置重启计数器时出错: {str(e)}")
    except Exception as e:
        print(f"最终清理时出错: {str(e)}")
    
    print(f"停止完成，共成功停止 {success_count}/{len(groups)} 个监控组")
    
    if success_count < len(groups):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main()) 