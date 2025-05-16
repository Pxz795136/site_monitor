# WAF监控系统

WAF监控系统用于监控多组URL的健康状态，并在URL不健康时发送告警。系统支持多组独立监控，每组可配置不同的监控参数。

## 功能特点

- 支持6个不同监控组的独立运行
- 每组可配置不同的监控参数
- 进程级隔离，避免单点故障
- 清晰的项目结构，便于管理和维护
- 进程标识清晰，易于区分不同监控组
- 脚本运行状态监控，确保监控进程持续运行
- 支持在开发环境(Mac)和生产环境(CentOS 7)无缝切换
- 详细的监控日志记录，包括URL状态变化和告警历史

## 系统架构

系统由以下主要模块组成：

- **监控模块**：检查URL健康状态
- **告警模块**：发送告警通知
- **工具模块**：提供配置加载、日志等通用功能
- **守护进程**：监控各监控进程的运行状态，自动重启异常退出的进程

## 目录结构

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
│   ├── group2.json           # 第二组配置
│   ├── group3.json           # 第三组配置
│   ├── group4.json           # 第四组配置
│   ├── group5.json           # 第五组配置
│   ├── group6.json           # 第六组配置
│   ├── targets_group1.txt    # 第一组监控目标
│   ├── targets_group2.txt    # 第二组监控目标
│   ├── targets_group3.txt    # 第三组监控目标
│   ├── targets_group4.txt    # 第四组监控目标
│   ├── targets_group5.txt    # 第五组监控目标
│   └── targets_group6.txt    # 第六组监控目标
├── logs/                     # 统一日志目录
│   ├── group1/               # 第一组日志
│   │   ├── monitor.log       # 监控状态日志
│   │   ├── health.log        # 健康状态日志
│   │   └── alert.log         # 告警日志
│   ├── group2/               # 第二组日志
│   ├── group3/               # 第三组日志
│   ├── group4/               # 第四组日志
│   ├── group5/               # 第五组日志
│   ├── group6/               # 第六组日志
│   ├── watchdog/             # 脚本监控日志
│   └── daemon/               # 守护进程日志
├── data/                     # 数据存储
│   ├── state_group1.json     # 第一组状态
│   ├── state_group2.json     # 第二组状态
│   ├── state_group3.json     # 第三组状态
│   ├── state_group4.json     # 第四组状态
│   ├── state_group5.json     # 第五组状态
│   ├── state_group6.json     # 第六组状态
│   └── watchdog.json         # 进程监控状态数据
├── bin/                      # 可执行脚本目录
│   ├── monitor_group1.py     # 第一组监控脚本
│   ├── monitor_group2.py     # 第二组监控脚本
│   ├── monitor_group3.py     # 第三组监控脚本
│   ├── monitor_group4.py     # 第四组监控脚本
│   ├── monitor_group5.py     # 第五组监控脚本
│   ├── monitor_group6.py     # 第六组监控脚本
│   ├── start_all.py          # 启动所有组的脚本
│   ├── stop_all.py           # 停止所有组的脚本
│   ├── status.py             # 查看所有组状态脚本
│   ├── watchdog.py           # 监控脚本运行状态
│   ├── crash_report.py       # 崩溃报告查询工具
│   ├── toggle_alerts.py      # 告警开关控制工具
│   ├── migrate_logs.py       # 日志迁移工具
│   └── install.py            # 安装依赖脚本
├── requirements.txt          # 项目依赖
└── README.md                 # 项目说明
```

## 安装部署

### 环境要求

- Python 3.6+
- 依赖包: 
  - requests - HTTP请求
  - psutil - 进程管理 
  - setproctitle - 进程标题设置
  - urllib3 - HTTP客户端
  - certifi - SSL证书
  - charset-normalizer - 字符编码
  - idna - 国际化域名支持
  - PyYAML - YAML格式支持
  - python-dateutil - 日期时间处理
  - pytz - 时区处理
  - six - Python 2/3兼容库

### 安装步骤

1. 克隆代码仓库

```bash
git clone <仓库地址> waf
cd waf
```

2. 安装依赖

```bash
python bin/install.py
```

### 配置说明

- `conf/global.json` 包含全局共享配置
- `conf/group*.json` 包含各组特定配置
- `conf/targets_group*.txt` 包含各组监控目标

配置文件示例:

```json
{
  "group_name": "group1",
  "monitor_interval": 60,
  "unhealthy_threshold": 2,
  "response_timeout": 2,
  "wechat_webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY",
  "enable_wechat_alert": true,
  "enable_email_alert": true
}
```

全局邮件配置支持多个收件人（以逗号或分号分隔）：

```json
{
  "smtp_server": "smtp.qq.com",
  "smtp_port": 587,
  "sender_email": "sender@example.com",
  "sender_password": "password",
  "receiver_email": "user1@example.com, user2@example.com; user3@example.com"
}
```

监控目标文件示例:

```
https://www.example.com/  ;示例站点1
https://api.example.com/  ;示例站点2
```

## 运行系统

### 启动所有监控组

```bash
cd site_monitor  # 先进入项目根目录
python3 start_all.py
```

### 在服务器环境中后台运行

start_all.py脚本本身已经实现了守护进程功能，可以在SSH断开连接后继续运行，无需使用nohup命令：

```bash
cd site_monitor  # 先进入项目根目录
python3 start_all.py
```

如果您仍然希望使用nohup命令（例如需要保存更详细的输出日志），可以使用以下命令：

```bash
cd site_monitor  # 先进入项目根目录
nohup python3 start_all.py > nohup.out 2>&1 &
```

您可以通过以下命令查看日志：

```bash
tail -f nohup.out
```

### 启动单个监控组

直接运行单个监控组脚本时，如果SSH连接断开，进程会被终止：

```bash
cd site_monitor  # 先进入项目根目录
python3 monitor_group1.py  # 注意：SSH断开连接后会终止
```

要让单个监控组在SSH断开后继续运行，请使用nohup命令：

```bash
cd site_monitor  # 先进入项目根目录
nohup python3 monitor_group1.py > logs/group1_startup.log 2>&1 &
```

您也可以使用screen或tmux工具来保持会话：

```bash
# 使用screen
screen -S monitor_group1
cd site_monitor  # 先进入项目根目录
python3 monitor_group1.py
# 按Ctrl+A然后按D分离会话

# 使用tmux
tmux new -s monitor_group1
cd site_monitor  # 先进入项目根目录
python3 monitor_group1.py
# 按Ctrl+B然后按D分离会话
```

### 停止所有监控组

```bash
cd site_monitor  # 先进入项目根目录
python3 stop_all.py
```

### 查看系统状态

```bash
cd site_monitor  # 先进入项目根目录
python3 status.py
```

## 日志说明

系统为每个监控组生成以下日志:

- `monitor.log` - 监控状态日志
- `health.log` - 健康状态日志
- `alert.log` - 告警日志
- `unhealthy.log` - 不健康状态日志

此外，监控守护进程生成:

- `watchdog.log` - 进程监控日志

系统采用日志轮转机制，每天午夜（0:00）会自动对日志文件进行轮转：
- 当前活动日志文件命名为`log_type.log`（例如`monitor.log`）
- 历史日志文件命名为`log_type.log.yyyy-mm-dd`（例如`monitor.log.2025-05-11`）
- 系统最多保留30天的历史日志，超过30天的日志会自动删除

## 维护说明

### 修改监控目标

编辑相应的目标文件 `conf/targets_group*.txt`，修改后系统会自动加载新的监控目标，无需重启。

### 修改配置参数

编辑相应的配置文件 `conf/group*.json`，系统会在下一个监控周期自动加载最新配置，无需重启。

### 管理告警通知开关

系统支持动态控制企业微信和邮件告警的开启/关闭，可以使用以下命令进行控制：

```bash
# 关闭所有组的企业微信告警
python bin/toggle_alerts.py --alert-type wechat --state off

# 开启group1的邮件告警
python bin/toggle_alerts.py --alert-type email --state on --scope group1

# 关闭全局配置中的所有告警
python bin/toggle_alerts.py --alert-type all --state off --scope global

# 开启所有配置文件中的所有告警
python bin/toggle_alerts.py --alert-type all --state on
```

修改告警开关后，系统会在下一个监控周期自动加载新配置，无需重启监控进程。

## 告警机制

当URL连续不健康次数达到阈值(`unhealthy_threshold`)时，系统会发送告警。URL被视为不健康的条件:

- HTTP状态码不是200
- 响应时间超过配置的超时时间
- 连接异常或其他错误

告警渠道:

- 企业微信机器人
- 邮件通知（支持多收件人）
- 可扩展其他告警方式

## 系统稳定性

系统设计具有以下稳定性保障措施：

1. **进程监控**：watchdog守护进程会监控所有监控组的运行状态，发现异常会自动重启
2. **线程守护机制**：每个监控组内有自我修复机制，能够检测并重启意外退出的监控线程
3. **异常处理增强**：完善的异常捕获和处理，确保单个URL异常不会影响整体监控
4. **状态持久化**：所有监控状态持久化保存，重启后能够恢复之前的状态
5. **配置热加载**：支持在不重启服务的情况下修改配置和监控目标

### 最新稳定性更新（2025-05-14）

最新版本对系统稳定性进行了以下增强：

1. 修改监控线程为非守护线程，防止主线程退出导致监控线程意外终止
2. 增加了线程状态检测机制，能够自动检测和恢复已停止的监控线程
3. 增强了异常处理机制，避免单个异常导致整个监控服务崩溃
4. 改进了日志记录，提供更详细的错误信息，方便故障排查

以上措施显著提升了系统在长时间运行中的稳定性，解决了之前在运行1-2小时后可能自动停止的问题。

## 异常诊断

系统内置了崩溃原因捕获和诊断功能，可以帮助您发现系统停止运行的原因。

### 崩溃原因捕获

当系统意外停止时，会自动记录详细的崩溃信息，包括：

- 崩溃类型（未捕获异常、系统信号、资源限制等）
- 异常堆栈跟踪
- 系统资源使用情况（内存、CPU）
- 崩溃时的系统状态

所有崩溃信息保存在 `logs/<group>/crashes/` 目录下，每次崩溃会生成一个独立的JSON文件。

### 查看崩溃报告

使用 `crash_report.py` 工具查看崩溃报告：

```bash
cd site_monitor  # 先进入项目根目录
# 列出指定组的所有崩溃记录
python3 crash_report.py group1

# 查看最近一次崩溃信息
python3 crash_report.py group1 --last

# 查看指定序号的崩溃记录详情
python3 crash_report.py group1 1

# 查看所有组的崩溃记录
python3 crash_report.py all
```

当系统重新启动时，如果检测到前一次运行是异常退出，会自动提示有崩溃记录，并指导如何查看详细信息。

### 崩溃预防

系统设计具有多种机制防止意外崩溃：

1. 心跳监控：定期记录进程活动状态，便于分析问题
2. 资源监控：监控内存和CPU使用情况，在资源过高时发出警告
3. 异常捕获：全局异常捕获机制，记录未处理的异常
4. 信号处理：捕获系统信号，记录终止原因
5. 线程状态监控：检测并自动重启已停止的监控线程