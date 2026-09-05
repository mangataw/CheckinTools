# CheckinTools

CheckinTools 是一个面向个人使用的可扩展自动签到工具，可通过 GitHub Actions 定时
运行，也可在本地使用 CLI 调试。

## 支持功能

- JavBus 论坛每日登录积分
- 福利吧签到
- V2EX 每日登录奖励
- 钉钉自定义群机器人通知
- 飞书自定义群机器人通知
- 多账号、失败隔离、每日两次执行与状态去重

## 青龙平台

青龙 Docker 可直接订阅本仓库，并分别创建 JavBus、福利吧和 V2EX 三个签到任务。
三个任务默认在容器当地时间 00:30 和 08:30 执行。订阅执行后会在
`/ql/data/config/checkin-tools.env` 首次初始化带注释的集中配置模板，后续更新不会覆盖。
在青龙「订阅管理 → 新建订阅」中可粘贴以下整行命令导入仓库参数：

```text
ql repo "https://github.com/mangataw/CheckinTools.git" "checkin_task_(javbus|fuliba|v2ex)[.]py" "" "checkin_base.py|checkin_setup.py|src" "main" "py"
```

把命令粘贴到新建订阅弹窗的「名称」输入框，待仓库参数自动展开后，将名称填为
`CheckinTools`，订阅更新定时规则填为 `15 3 * * *`，文件后缀填 `py`。「执行后」的
非定时初始化脚本会首次创建集中配置，并自动安装项目声明的 Python 依赖；具体字段和唯一值
路径见详细教程。

参阅 [青龙使用教程](docs/qinglong.md)。原 Actions/本地 CLI 配置及调度不变。

## GitHub Actions 使用

1. Fork 或复制本仓库。包含真实凭据时建议使用私有仓库。
2. 打开 **Settings → Secrets and variables → Actions**。
3. 按需添加 Repository secrets。
4. 在 **Actions → Daily check-in → Run workflow** 中先手动测试单个站点。
5. 确认无误后保留定时任务。

至少需要配置一个站点：

| Repository secret | 用途 |
| --- | --- |
| `JAVBUS_COOKIES` | JavBus，每行一个账号 Cookie |
| `FULIBA_USERNAMES` | 福利吧用户名，每行一个 |
| `FULIBA_COOKIES` | 福利吧 Cookie，与用户名按行对应 |
| `V2EX_USERNAMES` | V2EX 用户名，每行一个 |
| `V2EX_COOKIES` | V2EX 完整 Cookie，与用户名按行对应 |
| `DINGTALK_ACCESS_TOKEN` | 可选，钉钉 Webhook 中 `access_token=` 后的值 |
| `DINGTALK_SECRET` | 可选，钉钉加签密钥 |
| `FEISHU_WEBHOOK` | 可选，飞书完整 HTTPS Webhook |
| `FEISHU_SECRET` | 可选，飞书签名密钥 |

账号、Cookie、Token、Secret 和 Webhook 必须使用 Repository secrets。通知路由等
非敏感选项可使用 Repository variables：

| Repository variable | 默认值 | 说明 |
| --- | --- | --- |
| `CHECKIN_NOTIFY_CHANNEL` | `auto` | `auto`、`all`、`dingtalk` 或 `feishu` |
| `CHECKIN_NOTIFY_MODE` | `summary` | `summary` 或 `individual` |

多账号 Secret 直接输入真实换行，不使用逗号、JSON 或 YAML。

## 本地使用

需要 Python 3.10 或更高版本。

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Linux 或 macOS：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
```

编辑本地 `.env` 后运行：

```bash
python -m checkin_tools validate-config
python -m checkin_tools run --site all
python -m checkin_tools run --site javbus
python -m checkin_tools run --site fuliba
python -m checkin_tools run --site v2ex
python -m checkin_tools run --site all --no-notify
python -m checkin_tools notify-test --channel dingtalk
```

本地 `.env` 的多账号值可使用 `\n`：

```dotenv
JAVBUS_COOKIES="first-cookie\nsecond-cookie"
FULIBA_USERNAMES="first-user\nsecond-user"
FULIBA_COOKIES="first-cookie\nsecond-cookie"
V2EX_USERNAMES='first-user\nsecond-user'
V2EX_COOKIES='first-cookie\nsecond-cookie'
```

## 定时执行

默认计划时间为北京时间 09:00 和 14:00，不添加应用层随机延迟。GitHub Actions 的
计划任务仍可能受平台负载影响而延迟，因此实际开始时间不是严格的准点保证。

## 详细文档

- [JavBus 使用细则与 Cookie 获取](docs/javbus.md)
- [福利吧使用细则与 Cookie 获取](docs/fuliba.md)
- [V2EX 使用细则与 Cookie 获取](docs/v2ex.md)
- [钉钉与飞书通知配置](docs/notifications.md)
- [定时去重、安全与开发说明](docs/automation-and-development.md)

## 使用提示

- `.env`、Cookie、用户名、Token、Secret 和 Webhook 不应提交到 Git。
- Cookie 失效时，请重新登录并更新本地 `.env` 或 Repository secrets。
- 第三方站点可能存在网络、验证码、风控、页面结构和规则变化。
- 本项目主要服务于个人使用，不保证第三方站点长期兼容；使用者需自行遵守相关服务规则。

## License

[MIT](LICENSE)
