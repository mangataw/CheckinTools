# 新增签到站点指南

当前架构将站点接入收敛为三个手工部分：在统一清单声明站点、实现业务 Checker、补充行为测试和
站点专用说明。配置解析、Checker 注册、本地模板、GitHub Actions、青龙入口及公共文档索引由
`tools/sync_sites.py` 统一处理。

以下示例使用站点 ID `example`。ID 只能使用小写英文字母、数字和下划线，并应与 Checker 文件名
一致。

## 1. 确认任务适用

现有框架适合每个账号每天执行一次、能够验证“本次成功”或“今天已经完成”的任务。失败账号可在
当天后续调度中重试，账号凭据通过环境变量或青龙集中配置提供。

每小时监控、多阶段状态、文件产物、验证码或跨天队列需要独立任务语义，参阅
[非签到任务扩展边界](non-checkin-tasks.md)。

## 2. 在统一清单声明站点

只在 `src/checkin_tools/site_catalog.py` 的 `SITE_DEFINITIONS` 增加一项：

```python
SiteDefinition(
    site="example",
    display_name="Example",
    summary="Example 每日签到",
    documentation="docs/example.md",
    checker_module="checkin_tools.checkers.example",
    checker_class="ExampleChecker",
    qinglong_task_name="CheckinTools - Example 签到",
    credential_fields=(
        CredentialField(
            "username",
            "EXAMPLE_USERNAMES",
            "用户名",
            r"example_user_one\nexample_user_two",
            "Example 用户名，每行一个",
        ),
        CredentialField(
            "cookie",
            "EXAMPLE_COOKIES",
            "Cookie",
            r"example_cookie_one\nexample_cookie_two",
            "Example Cookie，与用户名按行对应",
        ),
    ),
    base_url_key="EXAMPLE_BASE_URL",
    default_base_url="https://example.com",
)
```

清单字段分别控制：

| 字段 | 用途 |
| --- | --- |
| `site` | CLI 参数、状态文件及青龙入口文件名 |
| `display_name` / `summary` | 运行结果和 README 展示文字 |
| `documentation` | README 中的站点文档链接 |
| `checker_module` / `checker_class` | 受信任的 Checker 加载路径 |
| `qinglong_task_name` / `qinglong_cron` | 青龙任务标题和调度；cron 不填时使用默认值 |
| `credential_fields` | 账号字段、环境变量、示例和说明；多个字段按行组合 |
| `base_url_key` / `default_base_url` | 可覆盖的 HTTPS 站点根地址 |

所有账号字段都按行读取。一个站点有多个字段时，每个变量必须具有相同的非空行数；通用配置层会
构造 `SiteAccount`，自动将字段加入脱敏集合，并让单站点运行忽略其他站点的无效配置。不需要修改
`config.py` 或新增账号数据类。

## 3. 实现 Checker

新建 `src/checkin_tools/checkers/example.py`：

```python
from __future__ import annotations

import time

import requests

from checkin_tools.config import AppConfig, SiteAccount
from checkin_tools.http import SafeHttpClient, UnsafeRedirectError
from checkin_tools.interfaces import Checker
from checkin_tools.models import CheckinResult, ResultStatus
from checkin_tools.site_catalog import site_definition

_SITE = site_definition("example")


class ExampleChecker(Checker):
    site = _SITE.site
    display_name = _SITE.display_name

    def __init__(self, config: AppConfig, client: SafeHttpClient | None = None) -> None:
        site_config = config.site(self.site)
        self._accounts = site_config.accounts
        self.client = client or SafeHttpClient(
            site_config.base_url,
            config.timeout_seconds,
            config.retries,
        )
        self._secrets = config.secrets()

    @property
    def accounts(self):
        return self._accounts

    def state_identity(self, account: SiteAccount):
        return account.secret_values()

    def check(self, account: SiteAccount, account_label: str) -> CheckinResult:
        started = time.monotonic()
        try:
            session = self.client.new_session()
            session.headers.update({"Cookie": account.cookie})
            # 验证登录身份，读取签到前状态，执行操作，再读取可确认的签到后证据。
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

Checker 使用 `account.value("字段名")` 读取任意声明字段；常用的 `username` 和 `cookie` 也提供同名
属性。业务实现必须满足以下约束：

- 每个账号创建独立 Session。
- 操作前验证凭据对应的登录身份。
- `SUCCESS` 必须来自操作后的站点证据，HTTP 200 本身不代表成功。
- `ALREADY_DONE` 必须来自操作前的当日证据，并且不能再次提交签到请求。
- 使用 `SafeHttpClient` 限制 HTTPS、目标主机和重定向。
- 日志、摘要和异常不能包含账号字段、Token 或带敏感查询参数的 URL。
- 网络错误可标记为可重试；身份失效、结构变化和不安全地址通常不可重试。

Checker 不需要在 `checkers/__init__.py` 再注册。构建器会根据清单中的模块和类名加载，并检查
Checker 的 `site` 是否一致。

## 4. 生成平台文件

完成清单声明后运行：

```bash
python tools/sync_sites.py
python tools/sync_sites.py --check
```

同步工具负责：

- 更新 `.env.example` 和 `qinglong/checkin-tools.env`。
- 创建 `qinglong/DefaultTasks/checkin_task_example.py`。
- 更新 GitHub Actions 手动站点选项和 Repository Secrets 映射。
- 更新 README 的站点列表、Secrets 表、运行命令和站点文档入口。
- 更新青龙教程的账号变量表和状态文件列表。
- 删除已从清单移除、且带生成标记的旧青龙入口。

生成文件及 `BEGIN GENERATED` / `END GENERATED` 区块不能手工维护。CI 会执行 `--check`，清单修改后
未提交生成结果会直接失败。

青龙订阅使用通用白名单 `checkin_task_[a-z0-9_]+[.]py`。已经采用该白名单的用户新增站点时无需
再次修改订阅；旧用户如果仍保存逐站点白名单，需要更新一次。订阅初始化脚本会把新变量追加到
现有持久化配置，但真实用户名、Cookie 和 Token 仍须由用户填写。GitHub Repository Secrets 也
必须由仓库管理员手工创建；同步工具只生成工作流引用。

## 5. 添加行为测试和站点说明

将脱敏响应放入 `tests/fixtures/`，并为 Checker 覆盖真正影响行为的边界：

- 未签到时执行请求并获得可靠证据，返回 `SUCCESS`。
- 操作前已经签到，返回 `ALREADY_DONE`，且不发送签到请求。
- Cookie 无效或登录身份不匹配，返回 `FAILED`。
- 页面结构变化或签到后缺少确认依据，返回 `FAILED`。
- 外部主机、HTTP 降级或不安全操作链接被阻止。
- 超时和连接错误不泄露凭据，并正确设置 `retryable`。
- 多账号 Session 和失败相互隔离。

新增 `docs/example.md`，说明参数、多账号格式、凭据获取方法、本地测试命令、成功判断依据、服务
日期时区以及验证码和风控限制。README 的文档链接由清单生成，文件内容仍需人工编写。

## 6. 完成检查

```bash
python tools/sync_sites.py --check
python -m ruff check .
python -m pytest --cov=checkin_tools --cov-report=term-missing
python -m checkin_tools run --site example --no-notify
```

提交前确认：

- [ ] 清单声明完整，生成文件已经同步。
- [ ] Checker 使用站点证据确认成功并正确处理已签到状态。
- [ ] fixture 和行为测试不含真实个人信息。
- [ ] 站点专用文档已经创建。
- [ ] GitHub 和青龙中的真实账号参数由管理员填写。
- [ ] 使用测试账号完成一次无通知实机验证，输出中没有凭据。

真实签到会改变外部账号状态，只在准备好测试凭据并授权后执行。随后分别验证 GitHub Actions 手动
任务和青龙独立任务。
