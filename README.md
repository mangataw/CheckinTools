# CheckinTools

CheckinTools 是一个面向个人使用的可扩展自动签到工具，支持通过 GitHub Actions 定时运行，也支持本地 CLI 调试。

当前支持：

- JavBus 论坛每日登录积分
- 福利吧签到
- 钉钉自定义群机器人通知
- 飞书自定义群机器人通知

本项目开放源代码并采用 MIT License，但主要服务于作者自用。不保证第三方站点接口、页面结构或签到规则长期可用。使用者需自行承担账号、Cookie 以及第三方服务规则相关风险。

## GitHub Actions 快速开始

1. Fork 或复制本仓库到自己的私有仓库；如果使用公开仓库，请特别注意 Actions 日志和协作者权限。
2. 打开仓库的 **Settings → Secrets and variables → Actions**。
3. 按下表创建所需的 Repository secrets。
4. 在 **Actions → Daily check-in → Run workflow** 中先手动选择单个站点验证。
5. 确认运行正常后保留定时任务。默认每天触发两次：北京时间 01:30 和 08:30；每次触发后会随机延迟 0–30 分钟。

至少需要配置一个站点。通知是可选的；一个通知渠道的两个字段必须同时配置或同时留空。

| Secret | 必需 | 说明 |
| --- | --- | --- |
| `JAVBUS_COOKIES` | JavBus 必需 | 每行一个账号 Cookie |
| `FULIBA_USERNAMES` | 福利吧必需 | 每行一个用户名 |
| `FULIBA_COOKIES` | 福利吧必需 | 每行一个 Cookie，顺序和数量必须与用户名一致 |
| `DINGTALK_ACCESS_TOKEN` | 钉钉通知必需 | Webhook 中 `access_token=` 后的值，不是完整 URL |
| `DINGTALK_SECRET` | 钉钉通知必需 | 自定义机器人加签 Secret |
| `FEISHU_WEBHOOK` | 飞书通知必需 | 自定义机器人完整 HTTPS Webhook |
| `FEISHU_SECRET` | 飞书通知必需 | 自定义机器人签名校验 Secret |

通知路由和消息模式使用 Repository variables（不是 Secrets），均可不配置：

| Variable | 默认值 | 说明 |
| --- | --- | --- |
| `CHECKIN_NOTIFY_CHANNEL` | `auto` | `auto`、`all`、`dingtalk` 或 `feishu` |
| `CHECKIN_NOTIFY_MODE` | `summary` | `summary` 汇总发送，或 `individual` 逐账号发送 |

`auto` 只启用一个已配置渠道：仅配置一个时使用该渠道；钉钉和飞书都配置时默认使用钉钉。设置为 `all` 才会同时发送到两个渠道。

多账号 Secret 请直接输入真实换行，例如：

```text
first-account-value
second-account-value
```

不要使用逗号分隔，也不要把全部配置封装成 JSON 或 YAML。

## 本地安装与运行

需要 Python 3.12 或更高版本。建议使用虚拟环境：

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Linux 或 macOS：

```bash
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
```

编辑 `.env` 后使用以下命令：

```text
python -m checkin_tools validate-config
python -m checkin_tools run --site all
python -m checkin_tools run --site javbus
python -m checkin_tools run --site fuliba
python -m checkin_tools run --site all --no-notify
python -m checkin_tools notify-test --channel all
python -m checkin_tools notify-test --channel dingtalk
python -m checkin_tools notify-test --channel feishu
```

本地 `.env` 中的多账号值可以使用双引号包裹的 `\n`：

```dotenv
JAVBUS_COOKIES="first-cookie\nsecond-cookie"
FULIBA_USERNAMES="first-user\nsecond-user"
FULIBA_COOKIES="first-cookie\nsecond-cookie"
```

可选配置：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `JAVBUS_BASE_URL` | `https://www.javbus.com` | JavBus HTTPS 基础地址 |
| `FULIBA_BASE_URL` | `https://www.wnflb2023.com` | 福利吧 HTTPS 基础地址 |
| `CHECKIN_TIMEOUT_SECONDS` | `20` | 单次 HTTP 请求超时秒数 |
| `CHECKIN_RETRIES` | `2` | 连接、超时和适当 5xx 响应的重试次数 |
| `CHECKIN_NOTIFY_CHANNEL` | `auto` | 通知渠道选择；两者都有时 `auto` 优先钉钉 |
| `CHECKIN_NOTIFY_MODE` | `summary` | `summary` 汇总，或 `individual` 逐账号通知 |

基础地址只接受 HTTPS，且不能包含账号信息、查询参数、片段或额外路径。携带 Cookie 的请求遇到跨主机或降级到 HTTP 的重定向时会直接失败。

## 通知机器人配置

### 钉钉

1. 在钉钉群的机器人设置中添加“自定义”机器人。
2. 安全设置选择“加签”。
3. 从 Webhook 中取得 `access_token`，保存为 `DINGTALK_ACCESS_TOKEN`。
4. 将加签密钥保存为 `DINGTALK_SECRET`。

### 飞书

1. 在飞书群设置中添加“自定义机器人”。
2. 开启签名校验。
3. 将完整 Webhook 保存为 `FEISHU_WEBHOOK`。
4. 将签名校验密钥保存为 `FEISHU_SECRET`。

默认每次运行向自动选中的一个渠道发送一条汇总。将 `CHECKIN_NOTIFY_MODE` 设为 `individual` 可改为每个账号单独发送；将 `CHECKIN_NOTIFY_CHANNEL` 设为 `all` 可同时启用两个渠道。一个渠道失败不会阻止另一个渠道，但最终退出码会标记失败。

## 每日两次执行与去重

- 第一次计划时间为北京时间 01:30，第二次为 08:30。
- 每次计划触发后随机等待 0–30 分钟，因此实际开始窗口分别约为 01:30–02:00 和 08:30–09:00。
- 第一次运行后只保存站点和匿名账号编号，不保存 Cookie、用户名或通知凭据。
- 成功、今日已签到或明确的非暂时性错误会被标记为当日终态，第二次运行直接跳过。
- 超时、连接失败等暂时性网络问题不会标记为终态，第二次运行会重试对应账号。
- 手动触发不读取定时任务状态，因此始终按选择的站点执行，便于排障。

当第二次运行发现所有账号都已有终态时，会正常退出且不重复通知。跨运行状态通过按日期隔离的 GitHub Actions Cache 保存，不包含任何账号凭据。

## 退出码

| 退出码 | 含义 |
| --- | --- |
| `0` | 所有已配置任务成功或今日已签到 |
| `1` | 至少一个签到或已配置通知失败 |
| `2` | 配置无效、请求的渠道未配置或没有可运行站点 |

单账号、单站点或单通知渠道失败不会中止其他任务。

福利吧会区分首次签到和重复进入：进入首页时已出现签到成功标记则返回“今日已签到”，
不会重复调用签到接口；否则调用签到接口，并以签到成功标记或积分变化确认本次成功。
JavBus 以“每天登录”积分记录的北京时间日期确认成功，并在日志中记录最后签到时间。

## Cookie 更新与故障排查

- **Cookie 失效**：在浏览器重新登录对应站点，更新仓库 Secret 或本地 `.env`，然后手动运行单站点任务。
- **福利吧用户名不匹配**：确认用户名与 Cookie 按相同行号一一对应，且没有多余空行。
- **页面结构变化**：如果日志提示找不到签到规则、函数或无法确认签到结果，先确认站点在浏览器中仍可正常签到，再提交 Issue 或更新解析逻辑。
- **危险重定向被阻止**：确认基础地址是否仍为站点当前官方 HTTPS 主机；不要为了绕过检查改成 HTTP。
- **机器人发送失败**：先执行 `notify-test`，再检查机器人是否仍在群内、Access Token/Webhook 与加签密钥是否成对更新。
- **无任务可运行**：执行 `validate-config`，确认至少配置了一个站点的完整账号数据。

第三方站点可能有地区、网络、验证码或风控限制。自动重试只用于短暂网络错误，不会反复尝试鉴权错误。

## 隐私与安全

- `.env`、Cookie、用户名、Token、Secret 和 Webhook 不应提交到 Git。
- 日志和通知仅使用 `account-1`、`account-2` 等匿名编号。
- GitHub Actions 会逐项注册日志遮罩；CI 不加载签到或通知 Secrets。
- HTTP 客户端保留 TLS 校验，限制重试，并阻止携带凭据的跨主机重定向。
- 提交前建议运行 Ruff、测试和 Secret 扫描。
- 如果凭据曾出现在提交、日志或公开页面中，请立即在对应站点或机器人后台撤销并轮换；仅从 Git 历史中删除并不足够。

## 开发验证

```bash
python -m ruff check .
python -m pytest --cov=checkin_tools --cov-report=term-missing
```

测试使用模拟 HTTP 与人工脱敏 HTML fixture，不使用真实账号或 Cookie。新增站点应实现统一 `Checker` 接口，并沿用配置校验、匿名日志、安全 HTTP 和故障隔离约束。

## License

[MIT](LICENSE)
