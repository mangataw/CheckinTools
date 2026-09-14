# 新增签到站点指南

普通 Python 签到站点的接入点只有静态清单、约定式 Checker、行为测试和站点说明。配置解析、CLI
选项、GitHub Actions 和青龙机器文件都从同一份清单派生。

以下示例使用站点 ID `example`。ID 只能包含小写字母、数字和下划线，并且必须与 Checker 文件名
一致。

## 1. 声明站点

在 `src/checkin_tools/sites.toml` 追加：

```toml
[[sites]]
id = "example"
display_name = "Example"
base_url = "https://example.com"

[sites.credentials]
username = "EXAMPLE_USERNAMES"
cookie = "EXAMPLE_COOKIES"
```

`qinglong_cron` 和 `state_timezone` 可省略并继承 `[defaults]`。需要站点专用设置时放在
`[sites.credentials]` 之前：

```toml
qinglong_cron = "15 1 * * *"
state_timezone = "UTC"
```

凭据表左侧是 Checker 使用的逻辑字段，右侧是部署平台环境变量名。字段数量不限，但至少一个；
同站点的非空字段按行组合，行数必须一致。基础地址变量自动推导为 `EXAMPLE_BASE_URL`。

清单不声明模块名、类名、任务文件名或文档路径：这些内容分别约定为
`checkin_tools.checkers.example`、`SiteChecker`、`checkin_task_example.py` 和 `docs/example.md`。

## 2. 实现 Checker

新建 `src/checkin_tools/checkers/example.py` 并导出 `SiteChecker`：

```python
from checkin_tools.catalog import SiteDefinition
from checkin_tools.config import AppConfig, SiteAccount
from checkin_tools.contracts import Checker
from checkin_tools.http_client import SafeHttpClient


class ExampleChecker(Checker):
    def __init__(
        self,
        config: AppConfig,
        client: SafeHttpClient | None = None,
        *,
        definition: SiteDefinition,
    ) -> None:
        self.site = definition.id
        self.display_name = definition.display_name
        site_config = config.site(self.site)
        self._accounts = site_config.accounts
        self.client = client or SafeHttpClient(
            site_config.base_url, config.timeout_seconds, config.retries
        )

    @property
    def accounts(self):
        return self._accounts

    def state_identity(self, account: SiteAccount):
        return account.secret_values()

    def check(self, account: SiteAccount, account_label: str):
        cookie = account.value("cookie")
        # 验证身份、签到前状态、操作结果和签到后证据，并返回 CheckinResult。
        ...


SiteChecker = ExampleChecker
```

Checker 必须为每个账号创建独立 Session，验证凭据对应的身份，并以站点证据区分 `SUCCESS`、
`ALREADY_DONE` 和 `FAILED`。所有携带凭据的请求使用 `SafeHttpClient`；异常、日志和摘要不能泄露
任何凭据。网络错误可以标记为可重试，身份失效、结构变化和不安全地址通常不可重试。

## 3. 生成机器配置

```text
python tools/sync_sites.py
python tools/sync_sites.py --check
```

同步工具只负责：

- `qinglong/checkin-tools.env` 的凭据空值、默认地址和公共运行参数；
- `qinglong/DefaultTasks/checkin_task_<id>.py` 的入口与 cron；
- GitHub Actions 的手动站点选项和 Repository Secret 引用；
- 删除已从清单移除且带生成标记的旧青龙任务。

README、普通文档和 GitHub Repository Secrets 不由同步工具生成。真实凭据必须由管理员在平台中
填写，工具不会接触或上传。

## 4. 测试与说明

将脱敏响应放入 `tests/fixtures/`，覆盖成功、已签到、身份失效、页面结构变化、不安全跳转、超时、
多账号隔离和日志脱敏。新建 `docs/example.md`，说明凭据格式、获取方式、成功判断、服务日期时区及
站点限制。

完成后运行：

```text
python tools/sync_sites.py --check
python -m ruff check .
python -m pytest --cov=checkin_tools --cov-report=term-missing
```

测试不得使用真实 Cookie、发送通知或执行真实签到。
