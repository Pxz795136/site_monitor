#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WAF监控 - 安装依赖脚本
支持多种安装方式，自动适应不同环境
"""

import os
import sys
import subprocess
import platform
import shutil
import time

# 添加项目根目录到Python路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)


def is_root():
    """
    检查是否以root权限运行
    
    @returns {bool} 是否为root权限
    """
    return os.geteuid() == 0 if hasattr(os, 'geteuid') else False


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


def detect_system_type():
    """
    检测系统类型
    
    @returns {str} 系统类型: 'rhel', 'debian', 'other'
    """
    if os.path.exists('/etc/redhat-release'):
        return 'rhel'  # RHEL/CentOS
    elif os.path.exists('/etc/debian_version'):
        return 'debian'  # Debian/Ubuntu
    else:
        return 'other'


def install_build_tools():
    """
    安装编译工具
    
    @returns {bool} 安装是否成功
    """
    print("正在检查编译工具...")
    
    # 检查gcc是否已安装
    gcc_path = shutil.which('gcc')
    if gcc_path:
        print(f"已检测到gcc: {gcc_path}")
        return True
    
    if not is_root():
        print("需要安装编译工具，但未使用root权限运行")
        print("请使用 sudo python3 bin/install.py 或安装必要的编译工具")
        return False
    
    print("未检测到gcc，尝试安装编译工具...")
    system_type = detect_system_type()
    
    try:
        if system_type == 'rhel':
            print("检测到RHEL/CentOS系统，安装gcc和python3-devel...")
            subprocess.check_call(['yum', 'install', '-y', 'gcc', 'python3-devel'])
            print("编译工具安装成功")
            return True
        elif system_type == 'debian':
            print("检测到Debian/Ubuntu系统，安装gcc和python3-dev...")
            subprocess.check_call(['apt-get', 'update'])
            subprocess.check_call(['apt-get', 'install', '-y', 'gcc', 'python3-dev'])
            print("编译工具安装成功")
            return True
        else:
            print("无法确定系统类型，请手动安装gcc和Python开发包")
            return False
    except subprocess.CalledProcessError as e:
        print(f"安装编译工具失败: {str(e)}")
        return False


def install_system_packages():
    """
    使用系统包管理器安装依赖
    
    @returns {bool} 安装是否成功
    """
    if not is_root():
        print("需要安装系统包，但未使用root权限运行")
        print("请使用 sudo python3 bin/install.py 或手动安装必要的系统包")
        return False
    
    print("尝试使用系统包管理器安装依赖...")
    system_type = detect_system_type()
    
    try:
        if system_type == 'rhel':
            print("检测到RHEL/CentOS系统")
            # 安装EPEL仓库
            subprocess.check_call(['yum', 'install', '-y', 'epel-release'])
            # 安装系统依赖
            subprocess.check_call(['yum', 'install', '-y', 'python3-psutil', 'python3-requests', 'python3-setuptools', 'python3-pip', 'python3-yaml', 'python3-dateutil'])
            return True
        elif system_type == 'debian':
            print("检测到Debian/Ubuntu系统")
            subprocess.check_call(['apt-get', 'update'])
            subprocess.check_call(['apt-get', 'install', '-y', 'python3-psutil', 'python3-requests', 'python3-setuptools', 'python3-pip', 'python3-yaml', 'python3-dateutil'])
            return True
        else:
            print("无法确定系统类型，无法使用系统包管理器")
            return False
    except subprocess.CalledProcessError as e:
        print(f"使用系统包管理器安装依赖失败: {str(e)}")
        return False


def install_pip_package(package_name, mirror_url=None):
    """
    使用pip安装单个包
    
    @param {str} package_name - 包名称
    @param {str} mirror_url - 镜像源URL
    @returns {bool} 安装是否成功
    """
    print(f"正在安装 {package_name}...")
    cmd = [sys.executable, "-m", "pip", "install", package_name]
    
    if mirror_url:
        cmd.extend(["-i", mirror_url])
    
    try:
        subprocess.check_call(cmd)
        return True
    except subprocess.CalledProcessError as e:
        print(f"安装 {package_name} 失败: {str(e)}")
        return False


def install_requirements(use_mirror=True):
    """
    使用pip安装requirements.txt中的所有依赖
    
    @param {bool} use_mirror - 是否使用镜像源
    @returns {bool} 安装是否成功
    """
    requirements_file = os.path.join(project_root, 'requirements.txt')
    
    if not os.path.exists(requirements_file):
        print(f"要求文件不存在: {requirements_file}")
        return False
    
    print(f"正在使用pip安装依赖...")
    
    # 设置镜像源
    mirror_url = "https://pypi.tuna.tsinghua.edu.cn/simple" if use_mirror else None
    if mirror_url:
        print(f"使用镜像源: {mirror_url}")
    
    try:
        cmd = [sys.executable, "-m", "pip", "install", "-r", requirements_file]
        if mirror_url:
            cmd.extend(["-i", mirror_url])
        
        subprocess.check_call(cmd)
        return True
    except subprocess.CalledProcessError as e:
        print(f"使用pip安装依赖失败: {str(e)}")
        return False


def install_minimal_requirements(use_mirror=True):
    """
    安装最小化的依赖集
    
    @param {bool} use_mirror - 是否使用镜像源
    @returns {bool} 安装是否成功
    """
    print("安装最小化依赖...")
    
    # 创建临时的最小化requirements文件
    temp_requirements = os.path.join(project_root, 'requirements_minimal.txt')
    
    try:
        with open(temp_requirements, 'w') as f:
            f.write("""
# 可能需要的额外包
setproctitle>=1.2.0
jsonschema>=3.2.0
            """)
        
        # 使用镜像源安装
        mirror_url = "https://pypi.tuna.tsinghua.edu.cn/simple" if use_mirror else None
        cmd = [sys.executable, "-m", "pip", "install", "-r", temp_requirements, "--skip-installed"]
        if mirror_url:
            cmd.extend(["-i", mirror_url])
        
        subprocess.check_call(cmd)
        
        # 清理临时文件
        if os.path.exists(temp_requirements):
            os.remove(temp_requirements)
        
        return True
    except Exception as e:
        print(f"安装最小化依赖失败: {str(e)}")
        # 清理临时文件
        if os.path.exists(temp_requirements):
            try:
                os.remove(temp_requirements)
            except:
                pass
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
    
    requirements = """# 网络和HTTP请求
requests>=2.25.0

# 系统和进程监控
psutil>=5.4.0
setproctitle>=1.2.0

# 工具库
python-dateutil>=2.8.0

# 邮件和消息发送
pyyaml>=5.4.0
jsonschema>=3.2.0

# 开发和测试
pytest>=6.2.0

urllib3>=1.26.0,<2.0.0
certifi>=2021.5.30
charset-normalizer>=2.0.0
idna>=2.10
pytz>=2021.1
six>=1.16.0
"""
    
    try:
        with open(requirements_file, 'w') as f:
            f.write(requirements)
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
    主函数 - 支持多种安装方式
    """
    start_time = time.time()
    
    print("=" * 60)
    print("WAF监控系统依赖安装")
    print("=" * 60)
    
    # 检查Python版本
    if not check_python_version():
        return 1
    
    # 创建目录结构
    print("\n[1/5] 创建目录结构...")
    if not setup_directories():
        return 1
    
    # 创建requirements.txt
    print("\n[2/5] 检查依赖文件...")
    if not create_requirements():
        return 1
    
    # 安装策略：先尝试系统包管理器，再尝试编译安装，最后尝试最小化安装
    print("\n[3/5] 安装依赖...")
    
    # 尝试方法1：使用系统包管理器安装
    system_install_ok = install_system_packages()
    if system_install_ok:
        print("系统包安装成功，安装额外的pip依赖...")
        pip_install_ok = install_minimal_requirements()
    else:
        # 尝试方法2：安装编译工具后使用pip安装
        print("\n系统包安装失败，尝试编译安装...")
        if install_build_tools():
            print("编译工具安装成功，尝试使用pip编译安装...")
            pip_install_ok = install_requirements()
        else:
            # 尝试方法3：直接使用pip安装（可能会失败）
            print("\n无法安装编译工具，尝试直接使用pip安装...")
            pip_install_ok = install_requirements()
            
            if not pip_install_ok:
                print("\n所有安装方法都失败了。请手动安装以下依赖：")
                print("1. 使用系统包管理器：")
                print("   sudo yum install -y epel-release python3-psutil python3-requests  # RHEL/CentOS")
                print("   sudo apt-get install -y python3-psutil python3-requests  # Debian/Ubuntu")
                print("2. 或安装编译工具后使用pip：")
                print("   sudo yum install -y gcc python3-devel  # RHEL/CentOS")
                print("   sudo apt-get install -y gcc python3-dev  # Debian/Ubuntu")
                print("   然后：")
                print("   pip3 install -r requirements.txt")
                return 1
    
    # 设置脚本可执行权限
    print("\n[4/5] 设置脚本权限...")
    if not set_script_permissions():
        print("警告：设置脚本权限失败，可能需要手动赋予可执行权限")
    
    # 检查psutil是否可正常导入
    print("\n[5/5] 验证安装...")
    try:
        import psutil
        print(f"psutil导入成功，版本: {psutil.__version__}")
    except ImportError:
        print("警告：无法导入psutil，系统可能无法正常运行")
    
    # 显示完成信息
    end_time = time.time()
    duration = end_time - start_time
    
    print("\n" + "=" * 60)
    print(f"安装完成！用时 {duration:.2f} 秒")
    
    print("\n可以通过以下命令启动系统:")
    print(f"  {sys.executable} {os.path.join(script_dir, 'start_all.py')}")
    print("\n或者启动单个监控组:")
    print(f"  {sys.executable} {os.path.join(script_dir, 'monitor_group1.py')}")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n安装被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n安装过程出现错误: {str(e)}")
        sys.exit(1) 