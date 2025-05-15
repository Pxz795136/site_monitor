#!/usr/bin/env python3
"""
告警开关控制脚本 - 用于快速开启/关闭企业微信和邮件告警功能
"""

import os
import sys
import json
import argparse

# 获取项目根目录
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

from waf_monitor import utils


def parse_args():
    """
    解析命令行参数
    
    @returns {argparse.Namespace} 解析后的参数
    """
    parser = argparse.ArgumentParser(description='WAF监控告警开关控制工具')
    
    # 告警类型
    parser.add_argument('--alert-type', '-t', choices=['wechat', 'email', 'all'], 
                        default='all', help='要操作的告警类型：企业微信(wechat)、邮件(email)或全部(all)')
    
    # 开关状态
    parser.add_argument('--state', '-s', choices=['on', 'off'], required=True,
                        help='设置告警为开启(on)或关闭(off)')
    
    # 作用范围
    parser.add_argument('--scope', '-c', choices=['global', 'group1', 'group2', 'group3', 'group4', 'group5', 'group6', 'all'],
                        default='all', help='设置配置文件范围：全局(global)、指定组或全部(all)')
    
    return parser.parse_args()


def toggle_alert(config_file, alert_type, state):
    """
    切换配置文件中的告警开关
    
    @param {str} config_file - 配置文件路径
    @param {str} alert_type - 告警类型：wechat, email, all
    @param {bool} state - 开关状态：True为开启，False为关闭
    @returns {bool} 操作是否成功
    """
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        changed = False
        
        if alert_type in ['wechat', 'all']:
            if 'enable_wechat_alert' in config or alert_type == 'all':
                config['enable_wechat_alert'] = state
                changed = True
        
        if alert_type in ['email', 'all']:
            if 'enable_email_alert' in config or alert_type == 'all':
                config['enable_email_alert'] = state
                changed = True
        
        if changed:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        
        return False
    
    except Exception as e:
        print(f"修改配置文件 {config_file} 时出错: {str(e)}")
        return False


def main():
    """
    主函数
    """
    args = parse_args()
    
    # 转换开关状态
    state = True if args.state == 'on' else False
    
    # 获取要修改的配置文件列表
    conf_dir = os.path.join(project_root, 'conf')
    config_files = []
    
    if args.scope == 'global' or args.scope == 'all':
        config_files.append(os.path.join(conf_dir, 'global.json'))
    
    if args.scope != 'global':
        groups = []
        if args.scope == 'all':
            groups = ['group1', 'group2', 'group3', 'group4', 'group5', 'group6']
        else:
            groups = [args.scope]
        
        for group in groups:
            config_files.append(os.path.join(conf_dir, f'{group}.json'))
    
    # 执行修改
    success_count = 0
    for config_file in config_files:
        if os.path.exists(config_file):
            if toggle_alert(config_file, args.alert_type, state):
                print(f"✅ 已成功修改 {config_file}")
                success_count += 1
            else:
                print(f"⚠️ {config_file} 未发生修改")
        else:
            print(f"❌ 配置文件不存在: {config_file}")
    
    # 输出总结
    alert_type_str = "企业微信告警" if args.alert_type == 'wechat' else "邮件告警" if args.alert_type == 'email' else "所有告警"
    state_str = "开启" if state else "关闭"
    
    print(f"\n📋 操作总结:")
    print(f"  告警类型: {alert_type_str}")
    print(f"  目标状态: {state_str}")
    print(f"  成功修改: {success_count}/{len(config_files)} 个配置文件")
    
    print("\n📝 提示: 告警开关修改已完成，系统将在下一个监控周期自动加载新配置。")


if __name__ == "__main__":
    main() 