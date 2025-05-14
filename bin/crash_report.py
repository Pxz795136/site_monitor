#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
崩溃报告工具 - 查看程序崩溃原因
"""

import os
import sys
import argparse
import json
from datetime import datetime

# 添加项目根目录到Python路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

# 先确认crash_handler模块存在
try:
    from waf_monitor import crash_handler
except ImportError:
    # 处理crash_handler模块不存在的情况
    print("错误: 无法导入crash_handler模块。")
    # 检查模块文件是否存在
    crash_handler_path = os.path.join(project_root, 'waf_monitor', 'crash_handler.py')
    if not os.path.exists(crash_handler_path):
        print(f"模块文件不存在: {crash_handler_path}")
        print("请确保waf_monitor目录下存在crash_handler.py文件")
    else:
        print(f"模块文件存在但无法导入，可能存在语法错误或依赖问题: {crash_handler_path}")
        print("尝试手动导入模块以查看具体错误...")
        try:
            # 尝试获取更具体的导入错误
            import waf_monitor
            print(f"已成功导入waf_monitor包，但无法导入crash_handler模块")
            print(f"可用模块: {dir(waf_monitor)}")
        except Exception as import_err:
            print(f"导入waf_monitor包失败: {import_err}")
    sys.exit(1)


def list_crashes(group_name):
    """
    列出指定组的所有崩溃记录
    
    @param {str} group_name - 监控组名称
    """
    crash_dir = os.path.join(project_root, 'logs', group_name, 'crashes')
    
    if not os.path.exists(crash_dir):
        print(f"未找到{group_name}的崩溃记录目录")
        return
    
    crash_files = [f for f in os.listdir(crash_dir) if f.endswith('.json')]
    
    if not crash_files:
        print(f"未找到{group_name}的崩溃记录")
        return
    
    # 按时间排序
    crash_files.sort(reverse=True)
    
    print(f"\n{'='*60}")
    print(f"{group_name} 崩溃记录列表 (共 {len(crash_files)} 条)")
    print(f"{'='*60}")
    print(f"{'序号':<6}{'时间':<20}{'崩溃类型':<15}{'描述':<40}")
    print(f"{'-'*60}")
    
    for i, crash_file in enumerate(crash_files[:20]):  # 只显示最近20条
        try:
            # 从文件名解析基本信息
            parts = crash_file.replace('.json', '').split('_')
            date_str = parts[1]
            time_str = parts[2]
            crash_type = '_'.join(parts[3:])
            
            # 格式化日期时间
            datetime_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]} {time_str[:2]}:{time_str[2:4]}:{time_str[4:]}"
            
            # 尝试读取文件获取更多信息
            crash_path = os.path.join(crash_dir, crash_file)
            with open(crash_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                crash_info = data.get('crash_info', '')
                # 截断描述
                if len(crash_info) > 37:
                    crash_info = crash_info[:37] + '...'
                
                print(f"{i+1:<6}{datetime_str:<20}{crash_type:<15}{crash_info:<40}")
        except Exception as e:
            print(f"{i+1:<6}{crash_file:<60} (解析错误: {str(e)})")
    
    print(f"{'='*60}")
    print(f"使用 'python bin/crash_report.py {group_name} 序号' 查看详细信息\n")


def show_crash_details(group_name, crash_index):
    """
    显示指定崩溃记录的详细信息
    
    @param {str} group_name - 监控组名称
    @param {int} crash_index - 崩溃记录索引
    """
    crash_dir = os.path.join(project_root, 'logs', group_name, 'crashes')
    
    if not os.path.exists(crash_dir):
        print(f"未找到{group_name}的崩溃记录目录")
        return
    
    crash_files = [f for f in os.listdir(crash_dir) if f.endswith('.json')]
    
    if not crash_files:
        print(f"未找到{group_name}的崩溃记录")
        return
    
    # 按时间排序
    crash_files.sort(reverse=True)
    
    if crash_index < 1 or crash_index > len(crash_files):
        print(f"无效的崩溃记录索引: {crash_index}，有效范围: 1-{len(crash_files)}")
        return
    
    # 获取指定的崩溃文件
    crash_file = crash_files[crash_index - 1]
    crash_path = os.path.join(crash_dir, crash_file)
    
    try:
        with open(crash_path, 'r', encoding='utf-8') as f:
            crash_data = json.load(f)
        
        # 格式化崩溃报告
        report = format_crash_report(crash_data)
        print(report)
    except Exception as e:
        print(f"读取崩溃记录失败: {str(e)}")


def format_crash_report(crash_data):
    """
    格式化崩溃报告为可读字符串
    
    @param {dict} crash_data - 崩溃数据
    @returns {str} 格式化的崩溃报告
    """
    report = []
    
    report.append("="*80)
    report.append(" "*30 + "崩溃报告详情")
    report.append("="*80)
    report.append("")
    
    # 基本崩溃信息
    report.append("--- 基本信息 ---")
    report.append(f"崩溃类型: {crash_data.get('crash_type', '未知')}")
    report.append(f"崩溃信息: {crash_data.get('crash_info', '未知')}")
    
    # 时间戳
    system_info = crash_data.get('system_info', {})
    timestamp = system_info.get('timestamp')
    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp)
            report.append(f"崩溃时间: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        except:
            report.append(f"崩溃时间: {timestamp}")
    
    report.append("")
    
    # 系统信息
    report.append("--- 系统信息 ---")
    report.append(f"平台: {system_info.get('platform', '未知')}")
    report.append(f"Python版本: {system_info.get('python_version', '未知')}")
    report.append(f"进程ID: {system_info.get('pid', '未知')}")
    report.append(f"进程名称: {system_info.get('process_name', '未知')}")
    report.append(f"工作目录: {system_info.get('working_directory', '未知')}")
    report.append("")
    
    # 资源使用情况
    memory_usage = system_info.get('memory_usage', {})
    if memory_usage and isinstance(memory_usage, dict):
        report.append("--- 内存使用情况 ---")
        readable = memory_usage.get('readable', {})
        if readable:
            report.append(f"物理内存: {readable.get('rss', '未知')}")
            report.append(f"虚拟内存: {readable.get('vms', '未知')}")
        
        report.append(f"内存使用率: {memory_usage.get('percent', '未知')}%")
        report.append("")
    
    cpu_usage = system_info.get('cpu_usage', {})
    if cpu_usage and isinstance(cpu_usage, dict):
        report.append("--- CPU使用情况 ---")
        report.append(f"CPU使用率: {cpu_usage.get('percent', '未知')}%")
        report.append(f"线程数: {cpu_usage.get('threads', '未知')}")
        report.append(f"用户态CPU时间: {cpu_usage.get('user_time', '未知')}s")
        report.append(f"系统态CPU时间: {cpu_usage.get('system_time', '未知')}s")
        report.append("")
    
    # 异常详情
    additional_info = crash_data.get('additional_info', {})
    if additional_info:
        if 'exception_type' in additional_info:
            report.append("--- 异常详情 ---")
            report.append(f"异常类型: {additional_info.get('exception_type', '未知')}")
            report.append("")
        
        # 堆栈跟踪
        if 'traceback' in additional_info or 'stack_trace' in additional_info:
            report.append("--- 堆栈跟踪 ---")
            traceback_str = additional_info.get('traceback') or additional_info.get('stack_trace') or '无堆栈信息'
            report.append(traceback_str)
            report.append("")
    
    return "\n".join(report)


def show_last_crash(group_name):
    """
    显示最近一次崩溃信息
    
    @param {str} group_name - 监控组名称
    """
    report = crash_handler.format_last_crash_report(group_name)
    print(report)


def main():
    """
    主函数
    """
    parser = argparse.ArgumentParser(description='崩溃报告查询工具')
    parser.add_argument('group', type=str, help='监控组名称 (group1, group2, group3, group4 或 all)')
    parser.add_argument('index', type=int, nargs='?', help='崩溃记录索引，不提供则列出所有记录')
    parser.add_argument('--last', '-l', action='store_true', help='显示最近一次崩溃信息')
    
    args = parser.parse_args()
    
    # 处理 group=all 的情况
    if args.group.lower() == 'all':
        groups = ['group1', 'group2', 'group3', 'group4']
    else:
        groups = [args.group]
    
    for group in groups:
        # 显示最近一次崩溃
        if args.last:
            show_last_crash(group)
        # 显示指定索引的崩溃详情
        elif args.index is not None:
            show_crash_details(group, args.index)
        # 列出所有崩溃记录
        else:
            list_crashes(group)


if __name__ == "__main__":
    main() 