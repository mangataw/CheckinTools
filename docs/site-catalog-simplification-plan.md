# 站点清单与生成流程简化计划

状态：已实施

计划顺序：第一阶段
后续计划：[公共模块结构整理计划](module-structure-cleanup-plan.md)

## 1. 目标

本计划将站点接入收敛为一个静态清单和一套约定式 Python Checker，解决当前新增站点时需要在
Python 集中清单、Checker、平台配置、公共文档和硬编码测试之间重复维护的问题。

完成后应满足：

- 站点 ID、展示名称、默认地址、凭据键、青龙定时和状态时区只在一份静态清单中定义。
- 凭据字段数量由站点实际需求决定，可以只有 Cookie，也可以包含用户名、手机号、密码或 Token。
- Python Checker 按站点 ID 约定加载，不再声明模块路径、类名或额外模块名单。
- GitHub Actions 和青龙所需的机器配置由清单生成。
- README 和普通说明文档不再由生成器大段改写。
- 现有站点 ID、环境变量、调度、状态、通知和退出码保持兼容。
- CLI 继续作为 Actions、青龙、测试和排障共用的执行入口，但不再重点宣传本地长期运行。

## 2. 非目标

本阶段不处理以下事项：

- 不增加 Shell 或 JavaScript 执行器。
- 不扫描目录自动发现所有脚本。
- 不解析 Python 文件头注释作为配置来源。
- 不自动上传真实 GitHub Repository Secrets。
- 不修改现有签到请求、页面解析和成功判断逻辑。
- 不改变通知协议、状态文件格式或用户现有凭据名称。
- 不同时进行公共模块的大规模移动；文件整理在第二阶段单独实施。

## 3. 目标目录

第一阶段完成后的关键结构：

```text
src/checkin_tools/
├─ sites.toml                  # 唯一站点静态清单
├─ site_catalog.py            # 清单读取、默认值合并和校验
├─ config.py                  # 根据清单读取真实环境变量值
├─ cli.py
├─ runner.py
└─ checkers/
   ├─ __init__.py             # 约定式加载器
   ├─ javbus.py
   ├─ fuliba.py
   └─ v2ex.py

tools/
└─ sync_sites.py              # 仅生成机器依赖配置

qinglong/
├─ checkin-tools.env          # 生成文件
└─ DefaultTasks/
   └─ checkin_task_*.py       # 生成文件

.github/workflows/
└─ checkin.yml                # 部分区块由生成器维护
```

`sites.toml` 放在 Python 包内，并作为 package data 发布。读取方使用 `importlib.resources`，不能
依赖调用命令时的当前目录。

## 4. 清单格式

完整目标示例：

```toml
schema_version = 1

[defaults]
qinglong_cron = "30 0,8 * * *"
state_timezone = "local"

[[sites]]
id = "javbus"
display_name = "JavBus"
base_url = "https://www.javbus.com"

[sites.credentials]
cookie = "JAVBUS_COOKIES"

[[sites]]
id = "fuliba"
display_name = "福利吧"
base_url = "https://www.wnflb2023.com"

[sites.credentials]
username = "FULIBA_USERNAMES"
cookie = "FULIBA_COOKIES"

[[sites]]
id = "v2ex"
display_name = "V2EX"
base_url = "https://www.v2ex.com"
qinglong_cron = "30 8,16 * * *"
state_timezone = "UTC"

[sites.credentials]
username = "V2EX_USERNAMES"
cookie = "V2EX_COOKIES"
```

TOML 中的 `[sites.credentials]` 属于它前面最近声明的 `[[sites]]`，不是全局配置。凭据使用独立
子表而不是内联表，使每个字段独占一行，便于增删、审查和查看 Git diff。

### 4.1 顶层字段

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `schema_version` | 是 | 清单格式版本；不支持的版本必须立即报错 |
| `defaults.qinglong_cron` | 是 | 普通站点的默认青龙五段 cron |
| `defaults.state_timezone` | 是 | 普通站点的状态日期时区，默认 `local` |

### 4.2 站点字段

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | 是 | 小写站点 ID，也是 CLI 值和 Checker 文件名 |
| `display_name` | 是 | 日志、通知和青龙任务中使用的名称 |
| `base_url` | 是 | 默认 HTTPS 站点根地址 |
| `credentials` | 是 | Checker 逻辑字段名到外部环境变量名的映射 |
| `qinglong_cron` | 否 | 站点专用调度；缺失时继承全局默认值 |
| `state_timezone` | 否 | 状态日期时区；缺失时继承全局默认值 |

以下内容不进入清单：

- Checker 模块路径：由 `id` 推导。
- Checker 类名：统一使用 `SiteChecker`。
- 青龙任务名：由 `display_name` 推导为 `CheckinTools - <名称> 签到`。
- 青龙任务文件名：由 `id` 推导为 `checkin_task_<id>.py`。
- 基础地址环境变量：由 `id` 推导为 `<ID>_BASE_URL`。
- 文档路径：约定为 `docs/<id>.md`。
- README 摘要、字段标签、示例和说明：由人工文档负责。

### 4.3 凭据映射

凭据子表左侧是 Checker 使用的稳定逻辑名称，右侧是部署平台使用的环境变量名：

```toml
[sites.credentials]
username = "FULIBA_USERNAMES"
cookie = "FULIBA_COOKIES"
```

Checker 只读取：

```python
account.value("username")
account.value("cookie")
```

配置层负责读取 `FULIBA_USERNAMES` 和 `FULIBA_COOKIES`。所有凭据字段默认均为敏感数据，必须
进入日志脱敏集合。暂不增加 `label`、`example`、`description` 或 `secret` 等字段。

## 5. Python 数据模型与读取

删除当前手写的 `SITE_DEFINITIONS` 内容和 `CredentialField`。`SiteDefinition` 保留为解析后的
只读模型，建议结构为：

```python
@dataclass(frozen=True, slots=True)
class SiteDefinition:
    id: str
    display_name: str
    base_url: str
    credentials: Mapping[str, str]
    qinglong_cron: str
    state_timezone: str

    @property
    def base_url_key(self) -> str:
        return f"{self.id.upper()}_BASE_URL"
```

`site_catalog.py` 对外继续提供等价查询能力：

```python
SITE_DEFINITIONS
SITE_IDS
SITE_CONFIG_KEYS
site_definition(site_id)
load_site_definitions()
```

其中常量全部从 `sites.toml` 解析生成，不再手工列出站点。

### 5.1 Python 3.10 兼容

Python 3.11 及以上使用标准库 `tomllib`；Python 3.10 使用 `tomli`：

```python
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
```

`pyproject.toml` 增加：

```toml
"tomli>=2,<3; python_version<'3.11'",
```

并声明包数据：

```toml
[tool.setuptools.package-data]
checkin_tools = ["sites.toml"]
```

## 6. 清单校验

加载清单时必须完成以下校验：

- `schema_version` 必须为受支持的整数版本。
- `[defaults]` 必须存在且字段类型正确。
- 至少声明一个站点。
- 站点 ID 必须完全匹配 `[a-z0-9_]+`。
- 站点 ID 不能重复。
- 展示名称不能为空。
- `base_url` 必须是无用户信息、路径、查询或片段的 HTTPS 根地址。
- 每个站点至少有一个凭据字段。
- 逻辑凭据名必须匹配 `[a-z][a-z0-9_]*`。
- 环境变量名必须匹配 `[A-Z][A-Z0-9_]+`。
- 环境变量名不能跨站点重复。
- 自动推导的 `<ID>_BASE_URL` 不能与任何凭据键冲突。
- cron 必须为五段非空表达式。
- `state_timezone` 必须为 `local` 或可由 `zoneinfo.ZoneInfo` 加载的时区。
- 不允许未识别的顶层、默认值或站点字段，避免拼写错误静默失效。

结构错误应在 CLI 启动、测试和 `sync_sites.py --check` 中给出包含站点 ID 与字段名的明确错误。

## 7. Checker 加载约定

清单本身就是可信站点白名单，不再维护 `BUILTIN_SITE_MODULES`，也不扫描整个目录。

对于站点 `fuliba`：

```text
模块：checkin_tools.checkers.fuliba
入口：SiteChecker
```

加载器执行：

```python
module = import_module(f"checkin_tools.checkers.{definition.id}")
checker_type = getattr(module, "SiteChecker", None)
checker = checker_type(config, definition)
```

并验证：

- 模块存在；
- `SiteChecker` 是 `Checker` 的子类；
- 实例的站点 ID 与传入定义一致；
- Checker 不再重复声明展示名称、环境变量或默认地址。

迁移初期允许保留现有类名，并增加别名：

```python
SiteChecker = FulibaChecker
```

最终是否重命名原类不影响约定式加载。

## 8. 配置值流向

清单只定义键，不保存真实值：

```text
sites.toml
   │
   ├─ 定义 username → FULIBA_USERNAMES
   ├─ 定义 cookie   → FULIBA_COOKIES
   │
   ├─ GitHub Actions 从 Repository Secrets 注入值
   └─ 青龙从持久化配置文件读取值
                         │
                         ▼
                config.py 按行组合账号
                         │
                         ▼
                Checker 读取逻辑字段
```

多账号字段继续使用逐行配对规则。一个站点有多个凭据字段时，每个非空配置必须具有相同的行数。
单站点执行只校验当前站点，不能被其他站点的无效配置阻断。

## 9. 同步工具边界

`tools/sync_sites.py` 只生成机器必须一致的文件或区块。

### 9.1 保留生成

- `qinglong/checkin-tools.env`：凭据空值、默认地址和公共运行参数。
- `qinglong/DefaultTasks/checkin_task_<id>.py`：每站点青龙入口及 cron 元数据。
- `.github/workflows/checkin.yml`：手动运行的站点选项。
- `.github/workflows/checkin.yml`：Repository Secret 到环境变量的引用。

生成器仍应删除已经从清单移除且带生成标记的旧青龙任务文件。

### 9.2 停止生成

- `.env.example`
- README 支持站点列表
- README Secret 表格
- README 命令示例
- README 文档索引
- `docs/qinglong.md` 站点变量表
- `docs/qinglong.md` 状态文件列表

删除对应渲染函数和生成区块标记。README 和普通文档只描述规则、入口和例子，不复制完整机器
清单；站点细节由 `docs/<id>.md` 维护。

## 10. GitHub Secrets 边界

同步工具可以生成：

```yaml
FULIBA_COOKIES: ${{ secrets.FULIBA_COOKIES }}
```

这只是工作流引用，不会在 GitHub 仓库设置中创建 Secret。Repository Secret 的名称和值由用户
同时提交，无法通过仓库内的静态文件创建一个等待填写的空键。

未来若确有需要，可以单独设计使用 `gh secret set` 的交互式初始化工具；它必须要求用户已经登录、
确认目标仓库并主动输入真实值。本阶段不实现，也不允许 `sync_sites.py` 接触真实凭据。

## 11. 本地运行定位

保留 CLI，因为 GitHub Actions 和青龙最终都调用同一执行入口，测试和站点排障也依赖它。调整为：

- CLI 是公共执行内核和开发诊断入口。
- README 不再把本地长期签到作为主要部署方式。
- 默认不自动加载项目根目录 `.env`。
- 删除生成的 `.env.example`。
- 测试直接传入环境映射，不读取真实环境凭据。
- 开发者仍可临时设置环境变量后执行 `python -m checkin_tools`。

保留现有 CLI 子命令、参数语义和退出码。

## 12. 状态时区

删除青龙公共入口中针对 `v2ex` 的硬编码分支，改为读取清单中的 `state_timezone`：

```python
def state_date(definition, now):
    if definition.state_timezone == "local":
        return now.astimezone().date().isoformat()
    return now.astimezone(ZoneInfo(definition.state_timezone)).date().isoformat()
```

V2EX 配置为 `UTC`，其他现有站点继承 `local`。状态文件路径和内容格式保持不变。

## 13. 测试计划

新增或调整以下结构测试：

1. 清单可以解析三个现有站点，且顺序稳定。
2. 默认 cron 和时区正确继承。
3. V2EX 正确覆盖 cron 和 UTC 时区。
4. 单字段、双字段和任意数量凭据均可解析。
5. 重复站点 ID 被拒绝。
6. 非法站点 ID 被拒绝。
7. 重复环境变量名被拒绝。
8. 非法环境变量名被拒绝。
9. 不安全基础地址被拒绝。
10. 未知字段和不支持的 schema 版本被拒绝。
11. 缺失 Checker 模块或 `SiteChecker` 时给出明确错误。
12. Checker 身份与清单不一致时失败。
13. 新增一个临时站点声明即可驱动配置解析、CLI 选项和静态平台生成。
14. `sync_sites.py --check` 能发现漂移且不写文件。
15. 生成器只修改 Actions 和青龙目标，不再修改 README 和普通文档。
16. GitHub Actions 不在 CI 工作流中引用签到凭据。
17. 青龙模板键与运行时允许键完全一致。
18. V2EX 状态仍在 UTC 零点换日。

原有 Checker、HTTP、安全、Runner、通知和状态行为测试必须继续通过。不得使用真实 Cookie 或发送
真实通知。

## 14. 实施步骤

### 阶段 A：建立静态清单

1. 新增 `src/checkin_tools/sites.toml`。
2. 在 `pyproject.toml` 声明 TOML 兼容依赖和 package data。
3. 为 `site_catalog.py` 增加读取、默认值合并、未知字段检查和结构校验。
4. 用清单生成 `SITE_DEFINITIONS`、`SITE_IDS` 和 `SITE_CONFIG_KEYS`。
5. 添加解析器单元测试；此时暂时保留旧声明作为对照测试。

### 阶段 B：切换运行时

1. `config.py` 改为遍历清单凭据映射。
2. `cli.py` 的站点选项继续来自 `SITE_IDS`。
3. `checkers/__init__.py` 改为按 ID 导入 `SiteChecker`。
4. 三个现有 Checker 接收对应 `SiteDefinition`。
5. Runner 保持现有账号隔离、状态和通知行为。
6. 青龙入口改为从清单读取状态时区。

### 阶段 C：收缩生成器

1. `sync_sites.py` 改为读取同一 TOML 清单。
2. 保留青龙模板、任务入口和 Actions 区块生成。
3. 删除 README、普通文档和 `.env.example` 的生成逻辑。
4. 从现有文件移除废弃生成标记并人工整理内容。
5. 运行同步并确认只产生预期差异。

### 阶段 D：删除旧定义

1. 删除 Python 内手写的 `SITE_DEFINITIONS`。
2. 删除 `CredentialField`。
3. 删除 `checker_module`、`checker_class`、`summary`、`documentation`、`qinglong_task_name` 等字段。
4. 删除测试中的具体 Checker 类元组和站点键硬编码。
5. 更新新增站点、架构、青龙和扩展策略文档。

## 15. 兼容要求

重构后必须保持：

- 站点 ID：`javbus`、`fuliba`、`v2ex`。
- 所有现有凭据和基础地址环境变量名。
- GitHub Repository Secret 名称。
- 青龙持久化配置路径和增量补充行为。
- 青龙任务文件名及已有 cron 行为。
- 状态文件名、版本和内容格式。
- V2EX UTC 服务日期语义。
- CLI 命令、参数和退出码。
- 日志脱敏、HTTPS 和同主机限制。
- 通知渠道和消息模式。

本阶段是内部配置来源重构，不要求用户迁移已有 Secrets 或青龙真实配置。

## 16. 验收标准

完成后执行：

```powershell
python tools/sync_sites.py
python tools/sync_sites.py --check
python -m ruff check .
python -m pytest --cov=checkin_tools --cov-report=term-missing
```

必须满足：

- 同步检查无漂移。
- Ruff 无错误。
- 全部测试通过且覆盖率不低于项目阈值。
- 安装后的包可以通过 package resources 读取 `sites.toml`。
- 三个现有 Checker 的模拟行为结果与重构前一致。
- 没有执行真实签到、通知或 Secret 上传。
- `git diff` 中不存在真实账号、Cookie、Token、Secret 或 Webhook。

## 17. 完成后的新增站点流程

新增普通 Python 签到站点只需要：

1. 在 `sites.toml` 添加一个 `[[sites]]` 和对应 `[sites.credentials]`。
2. 新建 `src/checkin_tools/checkers/<id>.py` 并导出 `SiteChecker`。
3. 添加脱敏 fixture 和行为测试。
4. 新建或更新 `docs/<id>.md`。
5. 运行同步、静态检查和测试。

不再修改 `config.py`、`cli.py`、Runner、Checker 名单、Actions Secret 映射或青龙任务入口。
