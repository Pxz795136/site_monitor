"""
工具函数模块 - 提供配置加载、日志设置和其他工具函数
"""

import os
import json
import logging
import logging.handlers
import sys
import platform
from pathlib import Path


def get_project_root():
    """
    获取项目根目录的绝对路径
    
    @returns {str} 项目根目录的绝对路径
    """
    # 获取当前模块文件的路径
    current_file = os.path.abspath(__file__)
    # 项目根目录是当前文件所在目录的上一级
    project_root = os.path.dirname(os.path.dirname(current_file))
    return project_root


def load_config(group_name, config_type='json'):
    """
    加载指定组的配置文件
    
    @param {str} group_name - 组名称（如group1, group2等）
    @param {str} config_type - 配置文件类型，'json'或'targets'
    @returns {dict|list} 配置数据，json返回字典，targets返回列表
    """
    project_root = get_project_root()
    
    if config_type == 'json':
        config_path = os.path.join(project_root, 'conf', f'{group_name}.json')
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logging.error(f"配置文件不存在: {config_path}")
            raise
        except json.JSONDecodeError:
            logging.error(f"配置文件格式错误: {config_path}")
            raise
    elif config_type == 'targets':
        target_path = os.path.join(project_root, 'conf', f'targets_{group_name}.txt')
        try:
            urls = []
            url_to_waf = {}
            with open(target_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):  # 忽略空行和注释
                        continue
                    parts = line.split(';')
                    url = parts[0].strip()
                    waf = parts[1].strip() if len(parts) > 1 else "未知WAF"
                    urls.append(url)
                    url_to_waf[url] = waf
            return urls, url_to_waf
        except FileNotFoundError:
            logging.error(f"目标文件不存在: {target_path}")
            raise
    else:
        raise ValueError(f"不支持的配置类型: {config_type}")


def load_global_config():
    """
    加载全局配置文件
    
    @returns {dict} 全局配置数据
    """
    project_root = get_project_root()
    global_config_path = os.path.join(project_root, 'conf', 'global.json')
    
    try:
        if os.path.exists(global_config_path):
            with open(global_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}  # 如果文件不存在，返回空字典
    except json.JSONDecodeError:
        logging.error(f"全局配置文件格式错误: {global_config_path}")
        raise


def merge_configs(global_config, group_config):
    """
    合并全局配置和组配置
    
    @param {dict} global_config - 全局配置
    @param {dict} group_config - 组配置
    @returns {dict} 合并后的配置，组配置优先
    """
    result = global_config.copy()
    result.update(group_config)  # 组配置覆盖全局配置
    return result


def setup_logging(group_name, log_types=None):
    """
    设置日志系统
    
    @param {str} group_name - 组名称
    @param {list} log_types - 日志类型列表，如['monitor', 'health', 'alert']
    @returns {dict} 包含各类型日志记录器的字典
    """
    if log_types is None:
        log_types = ['monitor', 'health', 'alert']
    
    project_root = get_project_root()
    logs_dir = os.path.join(project_root, 'logs', group_name)
    
    # 确保日志目录存在
    os.makedirs(logs_dir, exist_ok=True)
    
    loggers = {}
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    for log_type in log_types:
        logger = logging.getLogger(f"{group_name}_{log_type}")
        logger.setLevel(logging.INFO)
        
        # 清除已有的处理器，避免重复
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # 文件处理器，使用TimedRotatingFileHandler进行日志轮转
        log_file = os.path.join(logs_dir, f"{log_type}.log")
        file_handler = logging.handlers.TimedRotatingFileHandler(
            log_file, 
            when='midnight',
            interval=1,
            backupCount=30,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # 添加控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        loggers[log_type] = logger
    
    return loggers


def save_pid(group_name, pid=None):
    """
    保存进程ID到PID文件
    
    @param {str} group_name - 组名称
    @param {int} pid - 进程ID，默认为当前进程
    """
    if pid is None:
        pid = os.getpid()
    
    project_root = get_project_root()
    data_dir = os.path.join(project_root, 'data')
    
    # 确保数据目录存在
    os.makedirs(data_dir, exist_ok=True)
    
    pid_file = os.path.join(data_dir, f"{group_name}.pid")
    try:
        with open(pid_file, 'w') as f:
            f.write(str(pid))
        print(f"已成功写入PID文件: {pid_file}, PID: {pid}")
    except Exception as e:
        print(f"无法写入PID文件 {pid_file}: {str(e)}")
        # 尝试诊断问题
        try:
            if os.path.exists(pid_file):
                print(f"PID文件已存在但无法写入，权限: {os.stat(pid_file).st_mode}")
            else:
                print(f"PID文件不存在，尝试创建。目录权限: {os.stat(data_dir).st_mode}")
        except Exception as dir_error:
            print(f"诊断目录问题时出错: {str(dir_error)}")


def load_pid(group_name):
    """
    从PID文件加载进程ID
    
    @param {str} group_name - 组名称
    @returns {int|None} 进程ID，如果文件不存在则返回None
    """
    project_root = get_project_root()
    pid_file = os.path.join(project_root, 'data', f"{group_name}.pid")
    
    try:
        with open(pid_file, 'r') as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None


def is_process_running(pid):
    """
    检查指定PID的进程是否正在运行
    
    @param {int} pid - 进程ID
    @returns {bool} 如果进程正在运行则返回True，否则返回False
    """
    if pid is None:
        return False
        
    try:
        # 首先使用psutil检查进程是否存在
        import psutil
        if not psutil.pid_exists(pid):
            return False
            
        # 获取进程详细信息
        process = psutil.Process(pid)
        # 检查进程状态是否为running
        if process.status() in [psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD]:
            return False
            
        # 尝试获取进程信息，确保可以访问进程
        process.cpu_percent()
        return True
    except ImportError:
        # 如果没有psutil，回退到传统方法
        try:
            # 根据操作系统选择不同的检查方法
            if platform.system() == "Windows":
                # Windows的进程检查
                import ctypes
                kernel32 = ctypes.windll.kernel32
                SYNCHRONIZE = 0x00100000
                process = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
                if process:
                    kernel32.CloseHandle(process)
                    return True
                return False
            else:
                # Unix/Linux/MacOS的进程检查
                os.kill(pid, 0)  # 发送空信号检查进程是否存在
                return True
        except (OSError, ProcessLookupError):
            return False
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        # 进程不存在、无法访问或僵尸状态
        return False
    except Exception as e:
        logging.error(f"检查进程状态时出错: {str(e)}")
        return False


def save_state(group_name, state_data):
    """
    保存状态数据到文件
    
    @param {str} group_name - 组名称
    @param {dict} state_data - 要保存的状态数据
    """
    project_root = get_project_root()
    data_dir = os.path.join(project_root, 'data')
    
    # 确保数据目录存在
    os.makedirs(data_dir, exist_ok=True)
    
    state_file = os.path.join(data_dir, f"state_{group_name}.json")
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(state_data, f, ensure_ascii=False, indent=2)


def load_state(group_name):
    """
    从文件加载状态数据
    
    @param {str} group_name - 组名称
    @returns {dict|None} 状态数据，如果文件不存在则返回None
    """
    project_root = get_project_root()
    state_file = os.path.join(project_root, 'data', f"state_{group_name}.json")
    
    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None 