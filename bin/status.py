#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WAF监控 - 系统状态查看脚本
"""

import os
import sys
import time
import json
import argparse
from datetime import datetime

# 添加项目根目录到Python路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

from waf_monitor import utils
from waf_monitor import crash_handler

# 定义监控组
GROUPS = ['group1', 'group2', 'group3', 'group4']


def check_group_status(group_name, show_crash=False):
    """
    检查指定监控组的状态
    
    @param {str} group_name - 监控组名称
    @param {bool} show_crash - 是否显示崩溃信息
    @returns {dict} 状态信息
    """
    # 获取进程ID
    pid = utils.load_pid(group_name)
    
    # 检查进程是否运行
    is_running = False
    if pid:
        is_running = utils.is_process_running(pid)
    
    # 获取监控状态数据
    state_data = utils.load_state(group_name) or {}
    
    # 获取最后心跳时间
    last_activity_file = os.path.join(project_root, 'data', f"last_activity_{group_name}.json")
    last_activity_time = None
    last_activity_type = None
    
    if os.path.exists(last_activity_file):
        try:
            with open(last_activity_file, 'r', encoding='utf-8') as f:
                activity_data = json.load(f)
                timestamp = activity_data.get('timestamp')
                if timestamp:
                    try:
                        last_activity_time = datetime.fromisoformat(timestamp)
                    except:
                        last_activity_time = timestamp
                last_activity_type = activity_data.get('type')
        except:
            pass
    
    # 获取崩溃信息
    crash_info = None
    if show_crash:
        crash_info = crash_handler.check_last_crash(group_name)
    
    # 获取监控URL数量
    url_count = len(state_data) if state_data else 0
    
    # 计算不健康URL数量
    unhealthy_count = 0
    alerted_count = 0
    
    if state_data:
        for url, status in state_data.items():
            if status.get('count', 0) > 0:
                unhealthy_count += 1
            if status.get('alerted', False):
                alerted_count += 1
    
    # 生成结果
    result = {
        'group': group_name,
        'pid': pid,
        'running': is_running,
        'url_count': url_count,
        'unhealthy_count': unhealthy_count,
        'alerted_count': alerted_count,
        'last_activity_time': last_activity_time,
        'last_activity_type': last_activity_type,
        'crash_info': crash_info
    }
    
    return result


def format_group_status(status, verbose=False):
    """
    格式化组状态信息为可读字符串
    
    @param {dict} status - 状态信息
    @param {bool} verbose - 是否显示详细信息
    @returns {str} 格式化的状态信息
    """
    group = status['group']
    pid = status['pid']
    running = status['running']
    url_count = status['url_count']
    unhealthy_count = status['unhealthy_count']
    alerted_count = status['alerted_count']
    last_activity_time = status['last_activity_time']
    last_activity_type = status['last_activity_type']
    crash_info = status['crash_info']
    
    # 格式化最后活动时间
    if isinstance(last_activity_time, datetime):
        last_activity_time_str = last_activity_time.strftime('%Y-%m-%d %H:%M:%S')
    else:
        last_activity_time_str = str(last_activity_time) if last_activity_time else "未知"
    
    # 基本状态信息
    if running:
        status_str = f"[运行中] {group} (PID: {pid})"
        if last_activity_type == 'heartbeat':
            status_str += f" - 最后心跳: {last_activity_time_str}"
    else:
        status_str = f"[已停止] {group}"
        if last_activity_type:
            status_str += f" - 最后活动: {last_activity_type} ({last_activity_time_str})"
    
    # URL状态信息
    url_status = f"URL: 总数={url_count}"
    if url_count > 0:
        url_status += f", 不健康={unhealthy_count}, 已告警={alerted_count}"
    
    # 组合结果
    result = [status_str, url_status]
    
    # 崩溃信息
    if crash_info and verbose:
        crash_type = crash_info.get('crash_type', '未知')
        crash_info_str = crash_info.get('crash_info', '未知原因')
        crash_time = None
        
        # 尝试从系统信息中获取时间
        sys_info = crash_info.get('system_info', {})
        if sys_info and 'timestamp' in sys_info:
            try:
                crash_time = datetime.fromisoformat(sys_info['timestamp'])
                crash_time = crash_time.strftime('%Y-%m-%d %H:%M:%S')
            except:
                crash_time = sys_info['timestamp']
        
        if not crash_time and 'timestamp' in crash_info:
            crash_time = crash_info['timestamp']
        
        result.append(f"最近崩溃: 类型={crash_type}, 时间={crash_time}")
        result.append(f"崩溃原因: {crash_info_str}")
        result.append(f"查看详情: python bin/crash_report.py {group} --last")
    
    return "\n    ".join(result)


def main():
    """
    主函数
    """
    parser = argparse.ArgumentParser(description='WAF监控系统状态查看工具')
    parser.add_argument('--verbose', '-v', action='store_true', help='显示详细信息')
    parser.add_argument('--group', '-g', type=str, help='指定监控组')
    parser.add_argument('--watch', '-w', action='store_true', help='实时监控模式')
    parser.add_argument('--interval', '-i', type=int, default=5, help='刷新间隔(秒)')
    
    args = parser.parse_args()
    
    groups = [args.group] if args.group else GROUPS
    
    # 实时监控模式
    if args.watch:
        try:
            while True:
                os.system('clear' if os.name == 'posix' else 'cls')
                print(f"WAF监控系统状态 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print("=" * 70)
                
                for group in groups:
                    status = check_group_status(group, show_crash=True)
                    print(format_group_status(status, verbose=args.verbose))
                    print("-" * 70)
                
                print(f"\n按Ctrl+C退出，每{args.interval}秒刷新一次...")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n已退出监控模式")
    # 一次性显示模式
    else:
        print(f"WAF监控系统状态 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        for group in groups:
            status = check_group_status(group, show_crash=True)
            print(format_group_status(status, verbose=args.verbose))
            print("-" * 70)


if __name__ == "__main__":
    main() 