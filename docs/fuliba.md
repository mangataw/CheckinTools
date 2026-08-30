# 福利吧使用细则

## 配置

福利吧需要两项仓库机密或本地环境变量：

- `FULIBA_USERNAMES`
- `FULIBA_COOKIES`

两项必须具有相同的行数和顺序。用户名应与登录后页面显示的名称完全一致。

## 获取 Cookie

不要使用浏览器控制台的 `document.cookie`，应复制浏览器实际发送的请求头：

1. 在浏览器中登录福利吧。
2. 打开：

   ```text
   https://www.wnflb2023.com/forum.php?mobile=no
   ```

3. 打开开发者工具的 **Network** 面板并刷新页面。
4. 选择 `forum.php?mobile=no` 请求。
5. 在 **Request Headers** 中复制 `Cookie:` 后面的完整值。
6. 不要包含 `Cookie:` 前缀、URL、JSON 或外层引号。

## 执行

```bash
python -m checkin_tools run --site fuliba
python -m checkin_tools run --site fuliba --no-notify
```

## 首次签到与重复进入

检查器先读取首页并核对登录用户名：

- 如果进入首页时，`div.tip_c` 或 `#fx_checkin_menut` 已包含“今日已签到”、
  “签到成功”等标记，返回 `ALREADY_DONE`，不会再次调用签到接口。
- 如果尚未签到，则从 `fx_checkin()` 中提取同主机 HTTPS 签到链接并发送请求。
- 请求后再次读取首页并重新核对用户名。出现签到成功标记，或积分文本相较签到前
  发生变化，返回 `SUCCESS`。
- 提交后两项证据都不存在时返回 `FAILED`。

因此 `SUCCESS` 表示本次运行实际调用了签到接口并获得确认；`ALREADY_DONE` 表示
进入时已经完成签到。

## 常见问题

- **登录会话无效**：从已登录首页的 Network 请求重新复制完整 Cookie。
- **用户名不匹配**：确认 `FULIBA_USERNAMES` 与页面显示名称完全一致。
- **找不到签到函数或链接**：站点脚本结构可能发生变化。
- **提交后无法确认**：检查签到组件文案或积分节点是否发生变化。

