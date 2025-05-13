#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WAF监控 - 安装依赖脚本
"""

import os
import sys
import subprocess
import platform

# 添加项目根目录到Python路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)


def check_python_version():
    """
    检查Python版本是否满足要求
    
    @returns {bool} 版本是否满足要求
    """
    major = sys.version_info.major
    minor = sys.version_info.minor
    
    if major < 3 or (major == 3 and minor < 6):
        print(f"错误: Python版本必须 >= 3.6，当前版本是 {major}.{minor}")
        return False
    
    print(f"Python版本检查通过: {major}.{minor}")
    return True


def install_package(package_name):
    """
    安装Python包
    
    @param {str} package_name - 包名称
    @returns {bool} 安装是否成功
    """
    print(f"正在安装 {package_name}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        return True
    except subprocess.CalledProcessError as e:
        print(f"安装 {package_name} 失败: {str(e)}")
        return False


def install_requirements():
    """
    安装requirements.txt中的所有依赖
    
    @returns {bool} 安装是否成功
    """
    requirements_file = os.path.join(project_root, 'requirements.txt')
    
    if not os.path.exists(requirements_file):
        print(f"要求文件不存在: {requirements_file}")
        return False
    
    print(f"正在安装依赖...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_file])
        return True
    except subprocess.CalledProcessError as e:
        print(f"安装依赖失败: {str(e)}")
        return False


def create_requirements():
    """
    创建requirements.txt文件
    
    @returns {bool} 创建是否成功
    """
    requirements_file = os.path.join(project_root, 'requirements.txt')
    
    if os.path.exists(requirements_file):
        print(f"要求文件已存在: {requirements_file}")
        return True
    
    requirements = [
        "requests>=2.25.0",
        "psutil>=5.8.0",
        "setproctitle>=1.2.2",
        "urllib3>=1.26.0,<2.0.0",
        "certifi>=2021.5.30",
        "charset-normalizer>=2.0.0",
        "idna>=2.10",
        "PyYAML>=6.0",
        "python-dateutil>=2.8.2",
        "pytz>=2021.1",
        "six>=1.16.0"
    ]
    
    try:
        with open(requirements_file, 'w') as f:
            f.write("\n".join(requirements))
        print(f"已创建要求文件: {requirements_file}")
        return True
    except Exception as e:
        print(f"创建要求文件失败: {str(e)}")
        return False


def setup_directories():
    """
    设置必要的目录结构
    
    @returns {bool} 设置是否成功
    """
    required_dirs = [
        os.path.join(project_root, 'logs', 'group1'),
        os.path.join(project_root, 'logs', 'group2'),
        os.path.join(project_root, 'logs', 'group3'),
        os.path.join(project_root, 'logs', 'group4'),
        os.path.join(project_root, 'logs', 'watchdog'),
        os.path.join(project_root, 'data'),
    ]
    
    try:
        for directory in required_dirs:
            if not os.path.exists(directory):
                os.makedirs(directory)
                print(f"已创建目录: {directory}")
        return True
    except Exception as e:
        print(f"创建目录结构失败: {str(e)}")
        return False


def set_script_permissions():
    """
    设置脚本可执行权限
    
    @returns {bool} 设置是否成功
    """
    if platform.system() == 'Windows':
        print("在Windows系统上跳过设置可执行权限")
        return True
    
    script_files = [
        os.path.join(script_dir, 'monitor_group1.py'),
        os.path.join(script_dir, 'monitor_group2.py'),
        os.path.join(script_dir, 'monitor_group3.py'),
        os.path.join(script_dir, 'monitor_group4.py'),
        os.path.join(script_dir, 'start_all.py'),
        os.path.join(script_dir, 'stop_all.py'),
        os.path.join(script_dir, 'status.py'),
        os.path.join(script_dir, 'watchdog.py'),
        os.path.join(script_dir, 'install.py')
    ]
    
    try:
        for script in script_files:
            if os.path.exists(script):
                os.chmod(script, 0o755)  # 设置可执行权限
                print(f"已设置可执行权限: {script}")
        return True
    except Exception as e:
        print(f"设置脚本权限失败: {str(e)}")
        return False


def main():
    """
    主函数
    """
    print("=" * 50)
    print("WAF监控系统依赖安装")
    print("=" * 50)
    
    # 检查Python版本
    if not check_python_version():
        return 1
    
    # 创建目录结构
    if not setup_directories():
        return 1
    
    # 创建requirements.txt
    if not create_requirements():
        return 1
    
    # 安装依赖
    if not install_requirements():
        return 1
    
    # 设置脚本可执行权限
    if not set_script_permissions():
        return 1
    
    print("\n安装完成！可以通过以下命令启动系统:")
    print(f"  {sys.executable} {os.path.join(script_dir, 'start_all.py')}")
    print("\n或者启动单个监控组:")
    print(f"  {sys.executable} {os.path.join(script_dir, 'monitor_group1.py')}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 