# JavBus 使用细则

## 配置

JavBus 使用仓库机密或本地环境变量 `JAVBUS_COOKIES`。每行对应一个账号；本地
`.env` 可以用双引号包裹并以 `\n` 分隔多个 Cookie。

## 获取 Cookie

不要从浏览器控制台执行 `document.cookie` 获取配置。它可能缺少 `HttpOnly`、
特定 Domain 或特定 Path 下的 Cookie，也不能保证与浏览器实际请求一致。

推荐步骤：

1. 在浏览器中登录 JavBus。
2. 打开以下积分规则日志页：

   ```text
   https://www.javbus.com/forum/home.php?mod=spacecp&ac=credit&op=log&suboperation=creditrulelog
   ```

3. 打开开发者工具的 **Network** 面板并刷新页面。
4. 选择对应的 `home.php?...creditrulelog` 请求。
5. 在 **Request Headers** 中找到 `Cookie`。
6. 复制 `Cookie:` 后面的完整值，不要包含 `Cookie:` 前缀、URL、JSON 或外层引号。

页面源码中的非零 `discuz_uid` 可以辅助确认浏览器当前已登录，但不能代替完整请求
Cookie。

## 执行

```bash
python -m checkin_tools run --site javbus
python -m checkin_tools run --site javbus --no-notify
```

## 成功判断

检查器请求“每天登录”积分规则日志，并使用北京时间判断：

1. 页面必须包含 `每天登录` 或 `每天登錄` 规则。
2. 规则所在表格行必须至少有六列。
3. 第六列的最后执行时间必须包含当天日期。

成功日志会包含页面记录的最后签到时间。页面已有“今日已签到”等标记时返回
`ALREADY_DONE`，否则返回 `SUCCESS`。HTTP 200 本身不代表签到成功。

JavBus 请求使用浏览器型请求头，避免普通脚本 User-Agent 被导向年龄确认页。

## 常见问题

- **返回年龄确认页**：重新从上述积分页面的 Network 请求复制完整 Cookie。
- **登录会话无效**：确认浏览器能打开积分页并显示自己的登录状态，然后更新 Cookie。
- **找不到每天登录规则**：可能是页面结构或规则文案发生变化。
- **日期不是今天**：登录奖励尚未到账，检查账号状态及站点规则。

