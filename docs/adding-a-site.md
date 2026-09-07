# 新增签到站点指南

本文说明如何在当前架构中加入一个新的每日签到站点。以下示例使用站点标识 `example`；实际
标识建议使用小写英文字母、数字和下划线，并在代码、CLI、状态文件及平台入口中保持一致。

站点 ID、显示名称、青龙任务标题、凭据键和默认地址集中保存在 `site_catalog.py`。Checker 类、
账号解析、GitHub Actions 选项、青龙静态入口、模板及文档仍需显式维护，不能只添加一个
Checker 文件。

## 1. 开始前确认任务适用

现有框架适合以下任务：

- 每个账号每天完成一次操作。
- 能从页面或接口获取明确的“本次成功”或“今天已经完成”证据。
- 失败账号可以在当天后续定时执行中重试。
- 账号凭据可以通过环境变量或青龙集中配置提供。

如果任务需要每小时持续运行、多阶段状态、文件产物、人工验证码处理或跨天队列，先设计独立的
任务和状态语义，不要直接套用每日签到终态。

## 2. 定义配置

先在 `src/checkin_tools/site_catalog.py` 的 `SITE_DEFINITIONS` 增加站点定义，填写唯一站点 ID、
显示名称、青龙任务标题、凭据键、基础地址变量和默认 HTTPS 地址。

再在 `src/checkin_tools/config.py` 中完成以下修改：

1. 根据账号字段决定是否新增账号数据类。只有 Cookie 的站点可以直接使用字符串元组；用户名与
   Cookie 成对的站点应使用冻结的数据类。
2. 在 `AppConfig` 增加账号集合和基础地址等字段。
3. 在 `load_config()` 中拆分环境变量，并校验必填项、配对数量和允许范围。
4. 从 `site_definition()` 读取基础地址变量和默认值，并使用 `validate_base_url()` 校验。
5. 在 `AppConfig.secrets()` 中加入用户名、Cookie、Token 等需要脱敏的值。

例如，只有 Cookie 的站点通常需要：

```python
@dataclass(frozen=True, slots=True)
class AppConfig:
    example_cookies: tuple[str, ...]
    example_base_url: str
    # 其他已有字段
```

环境变量建议使用一致的前缀：

```dotenv
EXAMPLE_COOKIES="first-cookie\nsecond-cookie"
EXAMPLE_BASE_URL=https://example.com
```

同时更新根目录 `.env.example` 和 `qinglong/checkin-tools.env`。公开模板只能放占位值，不能提交
真实用户名、Cookie、Token、Webhook 或页面 fixture 中的个人信息。

青龙入口会拒绝模板之外的未知字段。站点目录中的凭据键和基础地址键会自动进入允许列表；若新增
的是站点目录之外的运行选项，仍需将其加入 `APP_CONFIG_KEYS` 或青龙专用配置键。旧用户的持久化
配置不会随订阅更新而自动增加字段；发布说明和站点文档需要列出应手动加入的配置项。

## 3. 实现 Checker

在 `src/checkin_tools/checkers/example.py` 新建检查器并实现 `Checker` 接口。最小结构如下：

```python
from __future__ import annotations

import time

import requests

from checkin_tools.http import SafeHttpClient, UnsafeRedirectError
from checkin_tools.interfaces import Checker
from checkin_tools.models import CheckinResult, ResultStatus
from checkin_tools.site_catalog import site_definition


_SITE = site_definition("example")


class ExampleChecker(Checker):
    site = _SITE.site
    display_name = _SITE.display_name

    def __init__(self, config, client: SafeHttpClient | None = None) -> None:
        self._accounts = config.example_cookies
        self.client = client or SafeHttpClient(
            config.example_base_url,
            config.timeout_seconds,
            config.retries,
        )

    @property
    def accounts(self):
        return self._accounts

    def check(self, account: str, account_label: str) -> CheckinResult:
        started = time.monotonic()
        try:
            session = self.client.new_session()
            session.headers.update({"Cookie": account})
            # 读取签到前状态、验证登录身份、执行签到并读取签到后状态。
            status = ResultStatus.SUCCESS
            summary = "checked in and confirmed"
            retryable = False
        except requests.Timeout:
            status = ResultStatus.FAILED
            summary = "request timed out"
            retryable = True
        except UnsafeRedirectError:
            status = ResultStatus.FAILED
            summary = "unsafe link or redirect blocked"
            retryable = False
        except requests.RequestException:
            status = ResultStatus.FAILED
            summary = "network request failed"
            retryable = True
        return CheckinResult(
            self.site,
            account_label,
            status,
            summary,
            max(0.0, time.monotonic() - started),
            retryable,
        )
```

示例中的业务部分只是结构占位，实际实现必须满足以下约束：

- 每个账号创建独立 Session，避免 Cookie 和请求状态相互污染。
- 使用 `SafeHttpClient` 生成和检查地址，携带凭据的请求不得绕过 HTTPS 与同主机限制。
- 操作前验证 Cookie 对应的登录身份或其他可靠登录状态。
- `SUCCESS` 必须有操作后的站点证据，HTTP 200 本身不能作为成功依据。
- `ALREADY_DONE` 必须来自操作前的当日状态证据，并且不能再提交签到请求。
- 页面结构变化、身份不符、缺少成功证据均返回 `FAILED`。
- 结果与异常信息不能包含用户名、Cookie、一次性 Token 或带敏感查询参数的完整 URL。
- 网络超时及连接错误可以标记 `retryable=True`；身份失效、结构变化和不安全地址通常不可重试。

Runner 会隔离未处理异常并进行脱敏，但 Checker 应优先把预期错误转换成稳定、无凭据的摘要。

## 4. 注册到核心 CLI

在 `src/checkin_tools/checkers/__init__.py` 导入新类，将类型加入 `_CHECKER_TYPES`，并按需加入
`__all__`。`build_checkers()` 会按站点目录顺序创建实例，并检查注册项与目录一致。CLI 的
`run --site` choices 会自动读取站点目录，不需要再单独修改。

此时以下命令应能够解析和运行：

```bash
python -m checkin_tools validate-config
python -m checkin_tools run --site example --no-notify
```

`validate-config` 检查整体配置。当前实现中，其他已填写站点的无效配置也可能阻止单站点运行。

## 5. 接入 GitHub Actions

修改 `.github/workflows/checkin.yml`：

1. 在 `workflow_dispatch.inputs.site.options` 中加入 `example`。
2. 在运行步骤的 `env` 中映射该站点所需 Repository secrets。
3. 只有非敏感选项才使用 Repository variables。

CI 工作流不得引用真实签到或通知 Secrets。同步更新 `tests/test_workflows.py`，验证新站点出现在
手动选择项中、所需 Secrets 只注入签到工作流，并继续保留最小权限。

## 6. 接入青龙

新增 `qinglong/DefaultTasks/checkin_task_example.py`：

```python
"""
cron: 30 0,8 * * *
new Env('CheckinTools - Example 签到');
"""

from checkin_base import run_site

if __name__ == "__main__":
    raise SystemExit(run_site("example"))
```

然后完成以下同步：

1. 更新 README 和 `docs/qinglong.md` 中订阅白名单的站点正则。
2. 更新青龙教程中的任务数量、入口文件、配置变量和状态文件说明。
3. 更新 `tests/test_qinglong_entry.py` 中入口文件、订阅匹配、配置模板和运行桥接断言。

青龙的站点合法性、账号配置判断和站点配置键会从站点目录读取，不需要维护另一份站点集合。

已保存旧订阅的用户需要手动更新白名单，新入口才会被青龙拉取并注册为任务。已有
`/ql/data/config/checkin-tools.env` 不会被模板覆盖，也需要根据升级说明手动增加新变量。

## 7. 添加测试 fixture 与行为测试

将脱敏后的站点响应放入 `tests/fixtures/`，并在 `tests/test_checkers.py` 或独立测试文件中覆盖真正
影响行为的边界：

- 未签到状态经过请求后得到可靠证据，返回 `SUCCESS`。
- 操作前已经签到，返回 `ALREADY_DONE`，且没有发送签到请求。
- Cookie 无效或登录身份不匹配，返回 `FAILED`。
- 页面结构改变或签到后没有确认依据，返回 `FAILED`。
- 外部主机、HTTP 降级或不安全操作链接被阻止。
- 超时和连接错误不泄露原始异常或凭据，并正确设置 `retryable`。
- 多账号使用独立 Session，账号失败不会影响其他账号。

同时更新配置、CLI、工作流和青龙入口测试。fixture 中删除用户名、Cookie、Token、邮箱、IP 等
真实信息；日期和余额等业务字段使用构造值。

## 8. 补充用户文档

新增 `docs/example.md`，至少说明：

- 所需配置及多账号格式。
- 从浏览器安全获取 Cookie 或 Token 的步骤。
- 本地无通知测试命令。
- `SUCCESS` 和 `ALREADY_DONE` 的具体判断依据。
- Cookie 失效、验证码、风控和页面结构变化等限制。

同步更新 README 的支持功能、Secrets 表、本地命令和详细文档列表。若站点的服务日期与调度日期
不同，应明确说明采用的时区以及它如何影响成功确认。

## 9. 完成检查

提交前按以下清单核对：

- [ ] 站点目录以及配置字段、校验、脱敏和两个配置模板已经同步。
- [ ] Checker 返回统一结果，并使用站点证据确认成功。
- [ ] 新 Checker 类型已注册，目录一致性检查和 CLI choices 已覆盖该站点。
- [ ] GitHub Actions 手动选项与 Secrets 映射已经添加。
- [ ] 青龙入口、订阅白名单和教程已经同步。
- [ ] 行为、配置、CLI、工作流及青龙测试已经覆盖。
- [ ] README 和独立站点文档已经更新。
- [ ] `python -m ruff check .` 通过。
- [ ] `python -m pytest --cov=checkin_tools --cov-report=term-missing` 通过。
- [ ] 使用测试账号执行 `--site example --no-notify`，确认不会泄露凭据。

真实签到测试可能改变外部账号状态，只在明确授权并准备好测试凭据后执行。测试成功后再分别验证
GitHub Actions 手动任务和青龙独立任务。
