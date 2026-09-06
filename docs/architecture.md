# 项目架构与目录说明

本文说明 CheckinTools 的代码边界、运行链路和主要扩展点。站点配置和实际使用方式以
README、各站点文档及青龙教程为准。

## 1. 整体结构

CheckinTools 使用同一套核心代码支持本地命令行、GitHub Actions 和青龙 Docker：

```text
本地 CLI ──────────────┐
GitHub Actions ─────────┼─> CLI 与配置校验 ─> Runner ─> Checker ─> 签到结果
青龙独立站点入口 ──────┘                         └──────> Notifier
                                      └───────────────> 每日状态
```

三个入口只负责提供运行参数、配置和状态文件位置。站点请求与成功判断都在
`src/checkin_tools/checkers/` 中实现，因此不同平台不会复制签到业务逻辑。

## 2. 目录职责

```text
CheckinTools/
├─ .github/workflows/
│  ├─ checkin.yml                 # GitHub Actions 定时与手动签到
│  └─ ci.yml                      # 静态检查、测试、覆盖率与凭据扫描
├─ docs/                          # 使用、部署和开发文档
├─ qinglong/
│  ├─ checkin-tools.env           # 青龙公开配置模板
│  └─ DefaultTasks/
│     ├─ checkin_base.py          # 青龙配置、状态、锁与 CLI 桥接
│     ├─ checkin_setup.py         # 首次配置及 Python 依赖初始化
│     └─ checkin_task_*.py        # 各站点的青龙定时入口
├─ src/checkin_tools/
│  ├─ checkers/                   # 站点账号、请求、解析与成功判断
│  ├─ notifiers/                  # 钉钉与飞书通知实现及消息格式
│  ├─ cli.py                      # 命令解析和运行入口
│  ├─ config.py                   # 环境变量读取、类型转换与严格校验
│  ├─ http.py                     # HTTPS、同主机重定向与有限重试
│  ├─ interfaces.py               # Checker 与 Notifier 接口
│  ├─ models.py                   # 签到、通知及整次运行的结果模型
│  ├─ registry.py                 # 实例映射与重复名称检查
│  ├─ runner.py                   # 站点选择、账号隔离和通知调度
│  ├─ security.py                 # 日志脱敏与 GitHub Actions 掩码
│  └─ state.py                    # 每日成功状态的读取和保存
├─ tests/                         # 核心代码、工作流与青龙入口测试
├─ .env.example                   # 本地配置示例
├─ pyproject.toml                 # 包信息、依赖和工具配置
└─ README.md                      # 项目入口和使用概览
```

## 3. 核心执行链路

### 3.1 配置加载

`config.load_config()` 从环境变量构建 `AppConfig`。本地运行默认先读取 `.env`；GitHub
Actions 直接注入 Secrets 和 Variables；青龙入口读取持久化的
`/ql/data/config/checkin-tools.env`，然后将解析结果传给 CLI，不再加载项目目录中的 `.env`。

配置层负责：

- 拆分多账号值并校验用户名与 Cookie 数量。
- 校验基础地址、超时、重试次数及通知选项。
- 汇总需要从日志和 CI 输出中遮罩的凭据。

配置采用整包校验。即使只选择一个站点，其他已填写配置中的格式错误也会阻止本次启动。

### 3.2 组件构建

`checkers.build_checkers()` 根据 `AppConfig` 创建内置站点检查器；
`notifiers.build_notifiers()` 根据通知配置选择钉钉、飞书或两者。`registry.py` 将实例转成按
站点或渠道名称索引的映射，并拒绝重复名称。

当前注册方式是显式导入与构建，不会自动扫描目录。新增 Python 文件本身不会自动出现在 CLI、
GitHub Actions 或青龙任务中。

### 3.3 账号执行与故障隔离

`Runner` 按站点和配置顺序执行账号，每个账号使用 `account-1`、`account-2` 等匿名标签。
单个检查器抛出的异常会转成该账号的失败结果，其余账号和站点继续执行。通知渠道也分别隔离，
一个渠道失败不会阻止另一个渠道发送。

检查器统一返回三种状态：

| 状态 | 含义 | 是否写入当日终态 |
| --- | --- | --- |
| `SUCCESS` | 本次请求完成签到并得到站点证据确认 | 是 |
| `ALREADY_DONE` | 进入站点时已经完成当天签到 | 是 |
| `FAILED` | 登录、网络、站点结构或成功证据校验失败 | 否 |

`retryable` 用于描述失败是否适合后续重试。当前 Runner 不根据该字段立即重跑账号；网络层会对
部分连接错误和服务端错误进行有限重试，定时任务的下一次执行也会重新处理未写入终态的账号。

### 3.4 通知

Runner 在本次存在实际执行结果时调用 Notifier。`summary` 模式为整次运行发送汇总；
`individual` 模式按账号结果分别发送。当天状态已经跳过的账号不会生成新结果，因此也不会因
该账号重复发送成功通知。

### 3.5 每日状态

核心状态文件只保存日期以及 `站点:匿名账号编号`，不保存 Cookie、用户名或通知凭据。
GitHub Actions 通过 Cache 在当天两次计划任务之间传递一个状态文件；手动运行默认不使用该
状态。青龙为每个站点保存独立状态文件，并使用单实例锁避免同站点任务重叠。

GitHub Actions 使用北京时间生成状态日期。青龙使用容器当地日期。站点自身仍可采用不同的
服务日期，例如 V2EX 使用 UTC 日期核对每日奖励流水；站点成功判断与调度去重日期是两个独立
概念。

## 4. 三种运行方式的边界

| 能力 | 本地 CLI | GitHub Actions | 青龙 Docker |
| --- | --- | --- | --- |
| 配置来源 | 项目根目录 `.env` 或进程环境 | Secrets 与 Variables | 持久化集中配置文件 |
| 定时调度 | 由用户自行安排 | 工作流 cron | 每站点任务文件 cron |
| 每日状态 | 仅显式传入状态参数时使用 | 计划任务使用 Cache | 每站点持久化文件 |
| 并发保护 | 无额外进程锁 | Actions concurrency | 每站点文件锁 |
| 单站点运行 | `--site` 参数 | 手动输入参数 | 独立任务入口 |

## 5. 安全边界

- 账号认证使用 Cookie，不在代码中保存账号密码。
- 携带凭据的请求只允许 HTTPS，并限制在配置的同一主机；跨主机及降级重定向会被阻止。
- 日志使用匿名账号编号，并对已知凭据、敏感赋值和带查询参数的 URL 进行遮罩。
- 测试使用模拟请求及脱敏 HTML fixture，CI 不读取真实签到和通知凭据。
- 青龙的真实配置位于持久化配置目录，订阅仓库中的文件仅作为首次初始化模板。

## 6. 当前扩展边界

新增同类签到站点通常可以复用 `Checker`、`SafeHttpClient`、`Runner`、通知和状态能力。站点列表
及其配置目前仍分布在配置模型、检查器构建、CLI 参数、GitHub Actions、青龙入口和配置模板中，
所以新增站点需要同步这些接入点。后续的新增站点指南将给出完整清单和最小实现示例。

当前状态模型围绕“每个账号每天一次”的签到任务设计。若加入下载、备份、监控或一天多阶段执行
的脚本，需要先定义新的任务结果和状态周期，不能直接假设现有每日终态语义适用。
