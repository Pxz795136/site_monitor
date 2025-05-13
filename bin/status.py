#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WAF监控 - 查看所有监控组状态
"""

import os
import sys
import json
import time
from datetime import datetime
import psutil

# 添加项目根目录到Python路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

from waf_monitor import utils


def get_group_status(group_name):
    """
    获取指定组的状态信息
    
    @param {str} group_name - 组名称
    @returns {dict} 状态信息
    """
    status = {
        'group_name': group_name,
        'running': False,
        'pid': None,
        'cpu_percent': None,
        'memory_percent': None,
        'start_time': None,
        'uptime': None,
        'url_count': 0,
        'target_file': os.path.join(project_root, 'conf', f'targets_{group_name}.txt'),
        'config_file': os.path.join(project_root, 'conf', f'{group_name}.json'),
        'state_file': os.path.join(project_root, 'data', f'state_{group_name}.json')
    }
    
    # 检查进程状态
    pid = utils.load_pid(group_name)
    status['pid'] = pid
    
    if pid and utils.is_process_running(pid):
        status['running'] = True
        
        # 获取进程信息
        try:
            process = psutil.Process(pid)
            status['cpu_percent'] = process.cpu_percent(interval=0.1)
            status['memory_percent'] = process.memory_percent()
            status['start_time'] = datetime.fromtimestamp(process.create_time()).strftime('%Y-%m-%d %H:%M:%S')
            uptime_seconds = time.time() - process.create_time()
            days, remainder = divmod(uptime_seconds, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)
            status['uptime'] = f"{int(days)}天 {int(hours)}小时 {int(minutes)}分钟 {int(seconds)}秒"
        except Exception as e:
            print(f"获取进程 {pid} 信息时出错: {str(e)}")
    
    # 加载URL数量
    try:
        urls, _ = utils.load_config(group_name, 'targets')
        status['url_count'] = len(urls)
    except Exception:
        pass
    
    # 加载状态文件
    try:
        state = utils.load_state(group_name)
        if state:
            status['url_health'] = state
    except Exception:
        pass
    
    # 添加watchdog状态信息（如果存在）
    watchdog_file = os.path.join(project_root, 'data', 'watchdog.json')
    if os.path.exists(watchdog_file):
        try:
            with open(watchdog_file, 'r', encoding='utf-8') as f:
                watchdog_data = json.load(f)
                if group_name in watchdog_data:
                    status['restart_count'] = watchdog_data[group_name].get('restart_count', 0)
                    status['watchdog_status'] = watchdog_data[group_name].get('status', '未知')
        except Exception:
            pass
    
    return status


def get_watchdog_status():
    """
    获取监控守护进程状态
    
    @returns {dict} 状态信息
    """
    status = {
        'running': False,
        'pid': None,
        'cpu_percent': None,
        'memory_percent': None,
        'start_time': None,
        'uptime': None,
        'groups': [],
        'state_file': os.path.join(project_root, 'data', 'watchdog.json')
    }
    
    # 查找watchdog进程
    watchdog_pid_file = os.path.join(project_root, 'data', 'watchdog.pid')
    try:
        if os.path.exists(watchdog_pid_file):
            with open(watchdog_pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            status['pid'] = pid
            
            # 检查进程是否存在
            if utils.is_process_running(pid):
                status['running'] = True
                
                # 获取进程信息
                try:
                    process = psutil.Process(pid)
                    status['cpu_percent'] = process.cpu_percent(interval=0.1)
                    status['memory_percent'] = process.memory_percent()
                    status['start_time'] = datetime.fromtimestamp(process.create_time()).strftime('%Y-%m-%d %H:%M:%S')
                    uptime_seconds = time.time() - process.create_time()
                    days, remainder = divmod(uptime_seconds, 86400)
                    hours, remainder = divmod(remainder, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    status['uptime'] = f"{int(days)}天 {int(hours)}小时 {int(minutes)}分钟 {int(seconds)}秒"
                except Exception as e:
                    print(f"获取进程 {pid} 信息时出错: {str(e)}")
    except Exception as e:
        print(f"检查watchdog状态时出错: {str(e)}")
    
    # 加载watchdog状态文件
    try:
        if os.path.exists(status['state_file']):
            with open(status['state_file'], 'r', encoding='utf-8') as f:
                watchdog_state = json.load(f)
                status['groups'] = list(watchdog_state.keys())
                status['state'] = watchdog_state
    except Exception as e:
        print(f"读取watchdog状态文件时出错: {str(e)}")
    
    return status


def print_status_table(group_statuses, watchdog_status):
    """
    打印状态表格
    
    @param {list} group_statuses - 组状态列表
    @param {dict} watchdog_status - 监控守护进程状态
    """
    print("\n" + "=" * 90)
    print("WAF监控系统状态")
    print("=" * 90)
    
    # 打印监控守护进程状态
    print("\n[监控守护进程]")
    print(f"运行状态: {'✅ 运行中' if watchdog_status['running'] else '❌ 已停止'}")
    if watchdog_status['running']:
        print(f"进程ID: {watchdog_status['pid']}")
        print(f"CPU占用: {watchdog_status['cpu_percent']}%")
        print(f"内存占用: {watchdog_status['memory_percent']:.2f}%")
        print(f"启动时间: {watchdog_status['start_time']}")
        print(f"运行时长: {watchdog_status['uptime']}")
        print(f"监控的组: {', '.join(watchdog_status['groups'])}")
    
    # 打印各监控组状态
    print("\n[监控组状态]")
    print("-" * 90)
    print("{:<10} {:<18} {:<10} {:<12} {:<12} {:<10} {:<10}".format(
        "组名", "状态", "进程ID", "CPU占用", "内存占用", "URL数量", "重启次数"
    ))
    print("-" * 90)
    
    # 标记是否有异常状态
    has_error = False
    
    for status in group_statuses:
        # 确定状态文本
        if 'watchdog_status' in status and status['watchdog_status'] == "已停止 - 超过最大重启次数":
            status_text = '⚠️ 超过最大重启次数'
            has_error = True
        elif status['running']:
            status_text = '✅ 运行中'
        else:
            status_text = '❌ 已停止'
            has_error = True
        
        # 显示重启计数
        restart_count = status.get('restart_count', '-')
        
        print("{:<10} {:<18} {:<10} {:<12} {:<12} {:<10} {:<10}".format(
            status['group_name'],
            status_text,
            status['pid'] if status['pid'] else '-',
            f"{status['cpu_percent']}%" if status['cpu_percent'] is not None else '-',
            f"{status['memory_percent']:.2f}%" if status['memory_percent'] is not None else '-',
            status['url_count'],
            restart_count
        ))
    
    print("-" * 90)
    
    # 如果有异常状态，显示处理建议
    if has_error:
        print("\n发现异常状态进程，可执行以下操作修复:")
        print("1. 运行 'python bin/start_all.py' - 将自动修复重启计数和重新启动所有进程")
        print("2. 运行 'python bin/stop_all.py' 然后 'python bin/start_all.py' - 完全停止后重新启动")
    
    print("\n")


def main():
    """
    主函数，显示所有监控组状态
    """
    # 从全局配置获取监控组列表
    try:
        global_config = utils.load_global_config()
        groups = global_config.get('monitor_groups', ['group1', 'group2', 'group3', 'group4'])
    except Exception as e:
        print(f"加载配置失败: {str(e)}")
        groups = ['group1', 'group2', 'group3', 'group4']
    
    # 获取监控守护进程状态
    watchdog_status = get_watchdog_status()
    
    # 获取各组状态
    group_statuses = []
    for group in groups:
        status = get_group_status(group)
        group_statuses.append(status)
    
    # 打印状态表格
    print_status_table(group_statuses, watchdog_status)
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 