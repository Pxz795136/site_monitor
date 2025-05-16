# WAF监控系统

WAF监控系统是一个用于监控多组URL健康状态的分布式监控解决方案，具有高可靠性、高可扩展性和故障自愈能力。本项目设计用于生产环境的长期稳定运行，支持多种告警机制和灵活的配置选项。

## 功能特点

- **多组独立监控**：支持6个不同监控组的隔离运行，避免单点故障
- **故障隔离设计**：每个监控组运行在独立进程中，单组故障不影响其他组
- **进程级监控**：守护进程自动监控和恢复异常退出的监控进程
- **线程级监控**：自动检测和恢复异常退出的监控线程
- **自我修复能力**：多层次的崩溃检测和恢复机制
- **配置热加载**：运行时动态更新配置和监控目标，无需重启
- **状态持久化**：监控状态持久化保存，支持重启后恢复
- **全面日志记录**：详细的分类日志，支持问题追踪和分析
- **跨平台兼容**：支持在开发环境(Mac)和生产环境(CentOS 7)无缝切换

## 系统架构

系统采用分层设计，主要由以下核心模块组成：

- **监控模块(monitor.py)**：负责URL健康检查，使用多线程并发监控多个URL
- **告警模块(alerter.py)**：处理告警判断逻辑和多渠道通知发送
- **工具模块(utils.py)**：提供配置加载、日志记录等通用功能
- **守护模块(watchdog.py)**：监控所有运行进程状态，自动重启异常进程
- **崩溃处理模块(crash_handler.py)**：捕获和记录系统崩溃信息

### 模块交互流程

1. **配置加载**：从配置文件加载监控参数和目标URL
2. **监控初始化**：创建线程池和监控对象
3. **健康检查**：定期检查URL健康状态
4. **状态判断**：评估URL状态变化和健康阈值
5. **告警触发**：当满足告警条件时，生成告警信息
6. **通知发送**：通过配置的渠道发送告警通知
7. **状态持久化**：定期保存监控状态到磁盘
8. **进程监控**：守护进程检查各监控进程状态，重启异常进程

## 代码结构

```
waf/
├── waf_monitor/              # 主要代码目录
│   ├── __init__.py
│   ├── monitor.py            # 监控核心逻辑
│   ├── alerter.py            # 告警处理模块
│   ├── utils.py              # 工具函数
│   ├── watchdog.py           # 脚本运行监控模块
│   └── crash_handler.py      # 崩溃处理模块
├── conf/                     # 配置目录
│   ├── global.json           # 全局共享配置
│   ├── group1.json           # 第一组配置
│   └── targets_group1.txt    # 第一组监控目标
├── logs/                     # 统一日志目录
│   ├── group1/               # 第一组日志
│   │   ├── monitor.log       # 监控状态日志
│   │   ├── health.log        # 健康状态日志
│   │   └── alert.log         # 告警日志
│   └── watchdog/             # 脚本监控日志
├── data/                     # 数据存储
│   ├── state_group1.json     # 第一组状态
│   └── watchdog.json         # 进程监控状态数据
├── bin/                      # 可执行脚本目录
│   ├── monitor_group1.py     # 第一组监控脚本
│   ├── start_all.py          # 启动所有组的脚本
│   ├── stop_all.py           # 停止所有组的脚本
│   ├── status.py             # 查看所有组状态脚本
│   └── install.py            # 安装依赖脚本
├── requirements.txt          # 项目依赖
└── README.md                 # 项目说明
```

## 技术实现

### 多线程监控设计

系统使用Python的`threading`模块实现多线程监控：

- 主线程负责管理和协调，监控线程负责具体URL检查
- 线程池模式控制并发度，避免资源耗尽
- 非阻塞IO提高响应效率，合理设置超时参数
- 线程状态监控机制检测并重启已停止的线程
- 实现线程同步以避免资源竞争和数据不一致

### 进程管理机制

系统采用进程级隔离策略，确保高可靠性：

- 每个监控组运行在独立进程中，使用`psutil`和`setproctitle`管理
- 守护进程使用进程ID文件和信号通信，检测进程存活
- 自动重启异常退出的进程，设置最大重启次数防止无限循环
- 优雅启动和停止机制，确保资源正确释放
- 进程名称自定义，便于监控和管理

### 状态持久化实现

系统使用JSON文件进行状态持久化：

- 定期将监控状态序列化为JSON格式，写入状态文件
- 启动时检查并加载状态文件，恢复上次运行的状态
- 文件写入采用原子操作，防止文件损坏
- 状态文件包含版本信息，支持向后兼容
- 定期清理过期状态数据，避免文件过大

### 崩溃监测和处理

系统实现多层次崩溃防护机制：

- 全局异常捕获：`try-except`包裹关键代码块
- 信号处理：捕获SIGTERM、SIGINT等系统信号
- 资源监控：定期检查内存和CPU使用情况
- 心跳机制：定期更新活动时间戳
- 崩溃报告生成：记录异常堆栈、系统信息和环境变量

### 告警机制实现

系统支持多种告警通知方式：

- 企业微信机器人：通过Webhook接口发送结构化消息
- 邮件通知：使用SMTP协议发送告警邮件，支持多收件人
- 可扩展接口：便于添加更多告警渠道
- 告警抑制：防止短时间内重复告警
- 告警分组：按监控组分类处理告警

## 开发环境

### 环境要求

- Python 3.6+（推荐使用Python 3.8+）
- 依赖包: 
  - requests==2.28.1 - HTTP请求
  - psutil==5.9.0 - 进程管理 
  - setproctitle==1.2.3 - 进程标题设置
  - urllib3==1.26.9 - HTTP客户端
  - certifi==2022.5.18.1 - SSL证书
  - charset-normalizer==2.0.12 - 字符编码
  - idna==3.3 - 国际化域名支持
  - PyYAML==6.0 - YAML格式支持
  - python-dateutil==2.8.2 - 日期时间处理
  - pytz==2022.1 - 时区处理
  - six==1.16.0 - Python 2/3兼容库

### 开发工具推荐

- 代码编辑器：Visual Studio Code或PyCharm
- 版本控制：Git
- 测试工具：pytest
- 日志分析：自定义日志分析脚本

## 高级功能

### 动态配置管理

系统提供多种运行时配置修改机制：

```python
# 动态修改告警开关示例
import json

def toggle_alert(config_file, alert_type, state):
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    if alert_type == 'wechat':
        config['enable_wechat_alert'] = state
    elif alert_type == 'email':
        config['enable_email_alert'] = state
    
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
```

### URL健康检查策略

系统实现了灵活的健康检查策略：

```python
# URL健康检查逻辑示例
def check_url_health(url, timeout):
    try:
        start_time = time.time()
        response = requests.get(url, timeout=timeout, verify=False)
        elapsed_time = time.time() - start_time
        
        is_healthy = response.status_code == 200 and elapsed_time < timeout
        status_code = response.status_code
        response_time = elapsed_time
        
        return is_healthy, status_code, response_time, None
    except Exception as e:
        return False, None, None, str(e)
```

### 告警通知扩展

系统支持自定义告警通知渠道：

```python
# 告警通知基类
class AlertNotifier:
    def __init__(self, config):
        self.config = config
    
    def send_alert(self, message):
        raise NotImplementedError("子类必须实现send_alert方法")

# 自定义告警通知实现
class CustomNotifier(AlertNotifier):
    def send_alert(self, message):
        # 实现自定义告警逻辑
        pass
```

## 稳定性保障

系统设计具有以下稳定性保障措施：

1. **进程监控**：watchdog守护进程会监控所有监控组的运行状态，发现异常会自动重启
2. **线程守护机制**：每个监控组内有自我修复机制，能够检测并重启意外退出的监控线程
3. **异常处理增强**：完善的异常捕获和处理，确保单个URL异常不会影响整体监控
4. **状态持久化**：所有监控状态持久化保存，重启后能够恢复之前的状态
5. **配置热加载**：支持在不重启服务的情况下修改配置和监控目标

### 最新稳定性更新

最新版本对系统稳定性进行了以下增强：

1. **非守护线程监控**：修改监控线程为非守护线程，防止主线程退出导致监控线程意外终止
2. **线程状态检测**：增加了线程状态检测机制，能够自动检测和恢复已停止的监控线程
3. **异常处理机制**：增强了异常处理机制，避免单个异常导致整个监控服务崩溃
4. **错误日志完善**：改进了日志记录，提供更详细的错误信息，方便故障排查

## 崩溃防护机制

系统实现了多层次的崩溃防护机制：

### 崩溃信息捕获

当系统意外停止时，会自动记录详细的崩溃信息：

```python
# 崩溃信息捕获示例
def capture_crash_info(exception=None):
    crash_info = {
        'timestamp': datetime.now().isoformat(),
        'process_id': os.getpid(),
        'process_name': setproctitle.getproctitle(),
        'system_info': {
            'platform': platform.platform(),
            'python_version': platform.python_version(),
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': psutil.virtual_memory().percent
        }
    }
    
    if exception:
        crash_info['exception'] = {
            'type': type(exception).__name__,
            'message': str(exception),
            'traceback': traceback.format_exc()
        }
    
    return crash_info
```

### 心跳监控

系统实现了心跳机制，定期记录活动状态：

```python
# 心跳监控示例
def update_heartbeat(group_name):
    heartbeat_file = f'data/last_activity_{group_name}.json'
    heartbeat_info = {
        'timestamp': datetime.now().isoformat(),
        'status': 'active'
    }
    
    with open(heartbeat_file, 'w') as f:
        json.dump(heartbeat_info, f)
```

## 日志管理

系统实现了完善的日志管理机制：

### 日志轮转

系统使用Python的`logging.handlers.TimedRotatingFileHandler`实现日志轮转：

```python
# 日志轮转配置示例
def setup_logger(name, log_file, level=logging.INFO):
    handler = logging.handlers.TimedRotatingFileHandler(
        log_file, when='midnight', interval=1, backupCount=30
    )
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    
    return logger
```

## 版本规划

### 当前版本

- 稳定的多组URL监控
- 微信和邮件告警通知
- 完善的崩溃诊断机制
- 自我恢复能力

### 未来版本计划

- 图形化管理界面
- 实时监控数据可视化
- 数据库存储监控结果
- RESTful API接口
- Docker容器化部署方案
- 更多告警通知渠道

## 贡献指南

欢迎参与项目开发，贡献方式包括：

1. 提交Bug报告
2. 功能建议和需求
3. 代码提交和Pull Request
4. 文档改进

请确保提交的代码符合项目的编码规范和测试要求。