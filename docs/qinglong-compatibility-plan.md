# 青龙兼容实施计划

状态：已在本地按 Linux Docker 青龙的仓库订阅方式重整，等待实机确认。

## 1. 规划修正

先前方案把入口文件散放在仓库根目录，导致订阅命令必须逐个列出三个任务和多个依赖；又让
运行脚本承担配置生成，造成订阅完成后配置文件仍不可见。这是部署规划问题。

参考 BiliBiliToolPro 的青龙目录和统一文件前缀，改为：

```text
qinglong/
  ├─ checkin-tools.env                 # 公开配置模板
  └─ DefaultTasks/
       ├─ checkin_task_javbus.py       # cron 30 0,8 * * *
       ├─ checkin_task_fuliba.py       # cron 30 0,8 * * *
       ├─ checkin_task_v2ex.py         # cron 30 0,8 * * *
       ├─ checkin_base.py              # 公共运行逻辑，不匹配任务白名单
       └─ checkin_setup.py             # 配置及依赖初始化，不匹配任务白名单
```

订阅白名单精确匹配三个站点入口，依赖文件匹配 `checkin_base.py|checkin_setup.py|src`。
不能依靠公共文件缺少 cron 元数据来阻止任务创建，因为青龙会为白名单匹配文件补默认定时。

## 2. 配置生命周期

订阅完成钩子调用 `checkin_setup.py`。它先以排他方式将公开模板首次复制到
`/ql/data/config/checkin-tools.env`，并通过 `pip install -e` 安装项目声明的依赖。用户编辑
的是青龙持久化配置目录中的副本，仓库更新只刷新模板，不覆盖真实配置。

三个签到任务只读取配置。缺失时给出明确错误，不再把“生成配置”作为一次签到任务。

## 3. 任务与原项目边界

- 青龙创建 JavBus、福利吧、V2EX 三个独立任务，默认每天 00:30、08:30。
- 每站点保留独立日志、启停、锁和状态文件。
- 复用现有 `src/checkin_tools` Checker、Runner、Notifier，不复制业务逻辑。
- 不调用青龙管理 API，不需要 client_id/client_secret。
- 不修改 `.github/workflows`、GitHub Actions cron、原 CLI 参数或 Actions 配置方式。

## 4. 验收

本地验证包括三个入口的 cron 元数据、公共文件不生成任务、统一订阅前缀、配置只复制一次、
自动依赖安装命令、模板参数完整性、每站点状态与锁、完整原测试回归，以及
`.github/workflows` 无本轮差异。

实机需要确认：一次订阅生成三个任务、执行后首次创建配置、再次更新不覆盖配置、三个任务
在容器当地时间 00:30 和 08:30 执行。
