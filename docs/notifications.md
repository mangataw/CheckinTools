# 通知配置细则

## 通知渠道

项目支持钉钉和飞书自定义机器人。每个渠道的两个参数必须同时配置或同时留空。

### 钉钉

使用仓库机密：

- `DINGTALK_ACCESS_TOKEN`
- `DINGTALK_SECRET`

`DINGTALK_ACCESS_TOKEN` 只能填写完整 Webhook 中 `access_token=` 后面的值，不能填写
完整 URL。`DINGTALK_SECRET` 填写开启“加签”后得到的签名密钥。

这两项属于敏感数据，必须放在 **Repository secrets**，不能放在明文
**Repository variables**。如果曾以明文变量保存，应删除旧变量并轮换机器人凭据。

### 飞书

使用仓库机密：

- `FEISHU_WEBHOOK`：完整 HTTPS Webhook
- `FEISHU_SECRET`：签名校验密钥

## 路由与消息模式

以下非敏感选项可配置为 Repository variables，也可以省略：

| Variable | 默认值 | 可选值 |
| --- | --- | --- |
| `CHECKIN_NOTIFY_CHANNEL` | `auto` | `auto`、`all`、`dingtalk`、`feishu` |
| `CHECKIN_NOTIFY_MODE` | `summary` | `summary`、`individual` |

`auto` 只选择一个已配置渠道；两者都有时优先钉钉。`all` 会同时发送到两个渠道。

## 测试

```bash
python -m checkin_tools notify-test --channel dingtalk
python -m checkin_tools notify-test --channel feishu
python -m checkin_tools notify-test --channel all
```

通知测试会真实发送消息。一个渠道失败不会阻止另一个渠道，但最终退出码会反映失败。

