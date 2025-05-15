#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WAF监控 - 日志文件迁移工具

此脚本用于将未归类的日志文件迁移到正确的目录结构中
"""

import os
import sys
import shutil
import logging

# 添加项目根目录到Python路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

# 设置日志记录器
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("migrate_logs")

def ensure_directories():
    """
    确保所有必要的目录存在
    """
    required_dirs = [
        os.path.join(project_root, 'logs', 'group1'),
        os.path.join(project_root, 'logs', 'group2'),
        os.path.join(project_root, 'logs', 'group3'),
        os.path.join(project_root, 'logs', 'group4'),
        os.path.join(project_root, 'logs', 'watchdog'),
        os.path.join(project_root, 'logs', 'daemon'),
    ]
    
    for directory in required_dirs:
        if not os.path.exists(directory):
            logger.info(f"创建目录: {directory}")
            os.makedirs(directory, exist_ok=True)

def migrate_logs():
    """
    迁移日志文件到正确的目录
    """
    logs_dir = os.path.join(project_root, 'logs')
    
    # 需要迁移的文件映射 {文件名: 目标目录}
    file_mappings = {
        'group1_startup.log': os.path.join(logs_dir, 'group1', 'startup.log'),
        'group2_startup.log': os.path.join(logs_dir, 'group2', 'startup.log'),
        'group3_startup.log': os.path.join(logs_dir, 'group3', 'startup.log'),
        'group4_startup.log': os.path.join(logs_dir, 'group4', 'startup.log'),
        'watchdog_startup.log': os.path.join(logs_dir, 'watchdog', 'startup.log'),
        'daemon.log': os.path.join(logs_dir, 'daemon', 'daemon.log'),
        'daemon_error.log': os.path.join(logs_dir, 'daemon', 'daemon_error.log'),
        'startup.log': os.path.join(logs_dir, 'daemon', 'startup.log'),
    }
    
    migrated_count = 0
    
    # 迁移文件
    for filename, target_path in file_mappings.items():
        source_path = os.path.join(logs_dir, filename)
        target_dir = os.path.dirname(target_path)
        
        if os.path.exists(source_path):
            # 确保目标目录存在
            os.makedirs(target_dir, exist_ok=True)
            
            # 如果目标文件已存在，备份它
            if os.path.exists(target_path):
                backup_path = f"{target_path}.bak"
                logger.info(f"备份现有文件到: {backup_path}")
                shutil.copy2(target_path, backup_path)
            
            # 移动文件
            logger.info(f"移动 {filename} 到 {target_path}")
            try:
                # 复制文件内容
                shutil.copy2(source_path, target_path)
                # 删除源文件
                os.remove(source_path)
                migrated_count += 1
            except Exception as e:
                logger.error(f"移动文件 {filename} 时出错: {str(e)}")
    
    return migrated_count

def main():
    """
    主函数
    """
    logger.info("开始迁移日志文件...")
    
    # 确保所有必要的目录存在
    ensure_directories()
    
    # 迁移日志文件
    migrated_count = migrate_logs()
    
    if migrated_count > 0:
        logger.info(f"成功迁移 {migrated_count} 个日志文件")
    else:
        logger.info("没有需要迁移的日志文件")
    
    logger.info("日志文件迁移完成")

if __name__ == "__main__":
    main() 