# CheckinTools

CheckinTools 是一个面向个人使用的可扩展自动签到工具，主要通过 GitHub Actions 或青龙定时
运行。命令行是两个平台共用的执行内核，也可用于开发和临时排障。

目前支持 JavBus、福利吧和 V2EX，并提供多账号隔离、每日状态去重、钉钉及飞书通知。各站点的
凭据、默认地址、青龙调度和状态时区以 `src/checkin_tools/sites.toml` 为机器清单；使用细节由对应
的 `docs/<站点 ID>.md` 维护。

## 青龙平台

青龙 Docker 可直接订阅本仓库，并为各站点分别创建签到任务。订阅执行后会在
`/ql/data/config/checkin-tools.env` 初始化集中配置；后续更新只补充缺失字段，不覆盖已有值。

在青龙「订阅管理 → 新建订阅」中粘贴：

```text
ql repo "https://github.com/mangataw/CheckinTools.git" "checkin_task_[a-z0-9_]+[.]py" "" "checkin_base.py|checkin_setup.py|src" "main" "py"
```

详细设置参阅 [青龙使用教程](docs/qinglong.md)。

## GitHub Actions 使用

1. Fork 或复制本仓库。包含真实凭据时建议使用私有仓库。
2. 在 **Settings → Secrets and variables → Actions** 中添加所需 Repository secrets。
3. 在 **Actions → Daily check-in → Run workflow** 中先手动测试单个站点。
4. 确认无误后保留定时任务。

当前站点凭据为：

| Repository secret | 用途 |
| --- | --- |
| `JAVBUS_COOKIES` | JavBus，每行一个账号 Cookie |
| `FULIBA_USERNAMES` | 福利吧用户名，每行一个 |
| `FULIBA_COOKIES` | 福利吧 Cookie，与用户名按行对应 |
| `V2EX_USERNAMES` | V2EX 用户名，每行一个 |
| `V2EX_COOKIES` | V2EX Cookie，与用户名按行对应 |
| `DINGTALK_ACCESS_TOKEN` / `DINGTALK_SECRET` | 可选钉钉通知，成对填写 |
| `FEISHU_WEBHOOK` / `FEISHU_SECRET` | 可选飞书通知，成对填写 |

同步工具只维护工作流中的 Secret 引用，不会在 GitHub 中创建或上传真实 Secret。多账号 Secret
使用真实换行，不使用逗号、JSON 或 YAML。

通知路由等非敏感选项可使用 Repository variables：

| Repository variable | 默认值 | 说明 |
| --- | --- | --- |
| `CHECKIN_NOTIFY_CHANNEL` | `auto` | `auto`、`all`、`dingtalk` 或 `feishu` |
| `CHECKIN_NOTIFY_MODE` | `summary` | `summary` 或 `individual` |

## 开发和排障

需要 Python 3.10 或更高版本：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

CLI 默认只读取进程环境，不自动加载项目根目录 `.env`。临时设置环境变量后可执行：

```text
python -m checkin_tools validate-config
python -m checkin_tools run --site javbus --no-notify
python -m checkin_tools run --site all
python -m checkin_tools notify-test --channel dingtalk
```

GitHub Actions 默认计划时间为北京时间 09:00 和 14:00；平台负载可能导致延迟。青龙任务的 cron
和状态日期时区来自站点清单。

## 详细文档

- [项目状态与验收记录](docs/project-status.md)
- [项目架构与目录说明](docs/architecture.md)
- [新增签到站点指南](docs/adding-a-site.md)
- [站点注册与插件机制决策](docs/extension-strategy.md)
- [非签到任务扩展边界](docs/non-checkin-tasks.md)
- [JavBus 使用细则与 Cookie 获取](docs/javbus.md)
- [福利吧使用细则与 Cookie 获取](docs/fuliba.md)
- [V2EX 使用细则与 Cookie 获取](docs/v2ex.md)
- [钉钉与飞书通知配置](docs/notifications.md)
- [定时去重、安全与开发说明](docs/automation-and-development.md)

## 使用提示

- Cookie、用户名、Token、Secret 和 Webhook 不应提交到 Git。
- 第三方站点可能存在网络、验证码、风控、页面结构和规则变化。
- 本项目主要服务于个人使用；使用者需自行遵守相关服务规则。

## License

[MIT](LICENSE)
