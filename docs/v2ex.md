# V2EX 使用细则与 Cookie 获取

## 配置

V2EX 使用浏览器登录后的完整 Cookie，不提交账号密码。每个用户名必须和同一行的
Cookie 对应：

```dotenv
V2EX_USERNAMES='first-user\nsecond-user'
V2EX_COOKIES='first-cookie\nsecond-cookie'
```

建议使用外层单引号，因为从浏览器复制的完整 Cookie 中，`A2` 值可能包含双引号。

GitHub Actions 中分别创建 `V2EX_USERNAMES` 和 `V2EX_COOKIES` Repository secrets，
多账号使用真实换行。

## 获取 Cookie

1. 在浏览器登录 `https://www.v2ex.com/`。
2. 打开开发者工具的 **Network（网络）** 面板并刷新页面。
3. 选择发往 `www.v2ex.com` 的文档请求。
4. 在 Request Headers 中复制完整的 `Cookie` 值，不要只复制单个 `A2` 字段。
5. Cookie 相当于登录凭据，只保存到本地 `.env` 或 GitHub Repository secrets。

## 首次本地测试

编辑 `.env` 后先执行：

```powershell
python -m checkin_tools validate-config
python -m checkin_tools run --site v2ex --no-notify
```

确认输出为成功或今日已领取，再配置 GitHub Actions secrets 并手动运行一次
**Daily check-in** 的 `v2ex` 选项。

## 实现与限制

程序访问 `/mission/daily`，验证 Cookie 对应的用户名，解析当前页面的一次性
`once` 领取链接，并在领取后重新访问任务页确认状态。所有携带 Cookie 的链接和
重定向都必须保持 HTTPS 且位于配置的同一主机。

Cookie 失效、站点验证码或风控、页面结构调整都可能导致失败。遇到登录状态无效时，
请在浏览器重新登录并更新 Cookie；程序不会自动登录或绕过验证码。
