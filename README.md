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

需要 Python 3.12 或更高版本。

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

默认计划时间为北京时间 01:30 和 08:30，每次触发后随机延迟 0–30 分钟。GitHub
Actions 的计划任务还可能受平台负载影响而进一步延迟。

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
