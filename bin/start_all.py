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

# 添加项目根目录到Python路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

from waf_monitor import utils


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
        # 启动进程
        process = subprocess.Popen(
            [python_executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            cwd=project_root
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


def main():
    """
    主函数，启动所有监控组
    """
    # 从全局配置获取监控组列表
    try:
        global_config = utils.load_global_config()
        groups = global_config.get('monitor_groups', ['group1', 'group2', 'group3', 'group4'])
    except Exception as e:
        print(f"加载配置失败: {str(e)}")
        groups = ['group1', 'group2', 'group3', 'group4']
    
    # 重置所有组的重启计数（自动修复）
    print("执行预检查：重置所有组的重启计数...")
    reset_all_restart_counts()
    
    # 首先启动各组监控，确保所有进程状态稳定
    success_count = 0
    for group in groups:
        if start_group(group):
            success_count += 1
    
    # 等待一段时间，确保所有进程都已经稳定运行
    print("等待所有监控进程稳定运行...")
    time.sleep(5)
    
    # 最后才启动watchdog进程
    print("正在启动监控进程守护程序...")
    watchdog_script = os.path.join(script_dir, 'watchdog.py')
    subprocess.Popen(
        [sys.executable, watchdog_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        cwd=project_root
    )
    
    print(f"启动完成，共成功启动 {success_count}/{len(groups)} 个监控组")
    
    if success_count < len(groups):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main()) 