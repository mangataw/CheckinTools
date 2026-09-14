# 公共模块结构整理计划

状态：已于 2026-09-14 实施

计划顺序：第二阶段
前置计划：[站点清单与生成流程简化计划](site-catalog-simplification-plan.md)

## 1. 目标

本计划在站点清单重构稳定后整理 `src/checkin_tools/` 的公共模块边界。目标不是增加目录层级，而是：

- 合并职责高度重叠的小模块。
- 删除已经失去作用的抽象和注册层。
- 让文件名直接表达职责。
- 保持核心包扁平，避免 `core/`、`services/`、`utils/` 等空泛分层。
- 保留 `checkers/` 和 `notifiers/` 两个真正会横向扩展的目录。
- 仅改变内部组织，不改变签到、通知、状态和平台行为。

## 2. 前置条件

开始本计划前，第一阶段必须已经完成并满足：

- `sites.toml` 是唯一站点清单。
- Checker 已按站点 ID 和统一 `SiteChecker` 入口加载。
- `CredentialField` 和手写站点定义已经删除。
- Actions 与青龙生成结果稳定。
- 全量测试和覆盖率检查通过。

模块移动不能与站点配置语义迁移混在同一个提交中，避免导入路径变化掩盖行为问题。

## 3. 当前模块职责判断

当前同级文件大多不是零散工具，而是被多个功能共同依赖的核心边界：

| 当前模块 | 实际职责 | 处理决定 |
| --- | --- | --- |
| `cli.py` | 命令解析和程序入口 | 保留 |
| `config.py` | 读取真实运行配置 | 保留 |
| `site_catalog.py` | 站点清单读取和校验 | 重命名为 `catalog.py` |
| `models.py` | 结果和报告数据结构 | 与接口合并 |
| `interfaces.py` | Checker/Notifier 契约 | 与模型合并 |
| `registry.py` | 实例列表转映射及重复检查 | 删除 |
| `runner.py` | 账号执行、隔离和通知编排 | 保留并吸收必要重复检查 |
| `http.py` | 安全 HTTP 传输 | 重命名为 `http_client.py` |
| `security.py` | 日志与异常脱敏 | 保留 |
| `state.py` | 每日状态和匿名账号键 | 保留 |
| `checkers/` | 可扩展站点实现集合 | 保留目录 |
| `notifiers/` | 可扩展通知实现集合 | 保留目录 |

## 4. 最终目标结构

```text
src/checkin_tools/
├─ __init__.py
├─ __main__.py
├─ sites.toml
├─ catalog.py                  # 静态清单读取、默认值和校验
├─ config.py                   # 环境变量和实际账号配置
├─ contracts.py                # 结果模型与扩展接口
├─ runner.py                   # 执行编排
├─ state.py                    # 每日状态持久化
├─ security.py                 # 脱敏和 CI mask
├─ http_client.py              # 安全 HTTP 客户端
├─ cli.py                      # 公共命令入口
├─ checkers/
│  ├─ __init__.py
│  ├─ javbus.py
│  ├─ fuliba.py
│  └─ v2ex.py
└─ notifiers/
   ├─ __init__.py
   ├─ common.py
   ├─ dingtalk.py
   └─ feishu.py
```

不新建以下目录：

```text
core/
domain/
services/
infrastructure/
adapters/
utils/
```

当前规模下，这些目录只会延长导入路径，不能形成足够稳定的独立子系统。

## 5. 合并 `models.py` 与 `interfaces.py`

两个模块共同定义 Checker、Notifier 和 Runner 之间的数据与行为契约，合并为 `contracts.py`。

目标内容：

```text
contracts.py
├─ ResultStatus
├─ CheckinResult
├─ NotificationResult
├─ RunReport
├─ Checker
└─ Notifier
```

目标导入形式：

```python
from checkin_tools.contracts import Checker, CheckinResult, ResultStatus
```

合并规则：

- 保持现有枚举值、数据类字段、默认值和 `RunReport.exit_code` 语义不变。
- 保持 Python 3.10 的 `StrEnum` 兼容实现。
- `Checker` 和 `Notifier` 继续使用抽象基类。
- Checker 的 `site` 与 `display_name` 改为实例属性，由清单定义注入。
- `state_identity()` 的默认行为保持兼容。
- 不在 `contracts.py` 引入配置、HTTP、状态或具体实现，避免反向依赖。

完成后删除 `models.py` 和 `interfaces.py`，统一更新生产代码和测试导入。

## 6. 删除 `registry.py`

当前注册模块只负责把实例列表转为字典并检查重复。完成站点清单重构后：

- 站点定义重复由 `catalog.py` 拒绝。
- Checker 模块来源由 `sites.toml` 决定。
- Checker 实例身份由加载器验证。
- 通知器数量很少，不需要独立注册抽象。

因此删除 `registry.py`。

Runner 在构造时直接完成最后一道实例检查：

```python
self.checkers = {}
for checker in checkers:
    if checker.site in self.checkers:
        raise ValueError(f"duplicate checker: {checker.site}")
    self.checkers[checker.site] = checker
```

通知器保持列表以保留配置顺序；构造时检查重复渠道：

```python
channels = [notifier.channel for notifier in notifiers]
if len(channels) != len(set(channels)):
    raise ValueError("duplicate notifier channel")
```

删除 `checker_map()`、`notifier_map()` 及对应直接测试，将重复检查测试迁移到 Runner 或通知构建器。

## 7. 重命名 `site_catalog.py`

重命名为 `catalog.py`，因为站点范围已经由 `sites.toml` 和 API 本身表达，较短名称更清楚：

```python
from checkin_tools.catalog import SITE_IDS, site_definition
```

迁移要求：

- 使用 `git mv` 保留文件历史。
- 更新 `config.py`、`cli.py`、Checker 加载器、青龙入口、同步工具和测试导入。
- 更新文档中的路径引用。
- 本阶段结束时不保留两个实现文件，避免形成兼容转发层。

项目当前未承诺稳定的第三方 Python API，因此内部导入可以一次性更新。用户环境变量、CLI 和部署
接口仍必须保持兼容。

## 8. 重命名 `http.py`

重命名为 `http_client.py`，明确它是带安全限制的 HTTP 客户端，而不是通用 HTTP 工具集合。

目标导入：

```python
from checkin_tools.http_client import SafeHttpClient, UnsafeRedirectError
```

保持以下行为不变：

- 只允许 HTTPS。
- 只允许配置的同一主机。
- 禁止跨主机或降级重定向。
- 限制重定向次数。
- 保留连接错误、超时和指定服务端状态重试。
- 每个账号仍由 Checker 创建独立 Session。
- 请求异常不得包含未脱敏凭据。

相应将 `tests/test_http.py` 重命名为 `tests/test_http_client.py`。

## 9. 保持独立的模块

### 9.1 `config.py`

只负责把环境或青龙配置中的真实值转换为应用配置：

- 账号逐行配对；
- 基础地址覆盖；
- 超时与重试；
- 通知配置；
- 单站点作用域；
- 敏感值集合。

它依赖 `catalog.py` 的参数定义，但 `catalog.py` 不得依赖 `config.py`，以保持静态清单可被同步工具
独立读取。

### 9.2 `state.py`

继续单独负责：

- 匿名稳定账号键；
- 每日终态集合；
- JSON 读取和写入；
- 状态版本兼容。

它可以依赖 `contracts.py` 的结果类型，但不能依赖 Runner、Checker 或平台入口。

### 9.3 `security.py`

继续单独负责：

- 已知凭据替换；
- 敏感赋值脱敏；
- URL 查询参数移除；
- 日志过滤器；
- GitHub Actions mask 注册。

它不能变成包含无关帮助函数的通用 `utils.py`。

### 9.4 `runner.py`

继续负责：

- 选择全部或单个站点；
- 多账号顺序执行；
- 稳定状态键和旧键兼容；
- Checker 异常隔离；
- 通知调用和渠道异常隔离；
- 汇总运行报告。

除吸收很小的重复实例检查外，不把 HTTP、配置解析、状态序列化或通知格式放进 Runner。

## 10. 保留的扩展目录

### 10.1 `checkers/`

Checker 是按站点横向增长的实现集合，应继续独立成目录。每个文件只包含该站点的：

- 请求头和路径；
- 登录身份验证；
- 签到前状态；
- 签到操作；
- 签到后证据；
- 站点特有响应解析；
- 站点特有异常摘要。

通用 HTTP、安全、状态和通知逻辑不得复制进 Checker。

### 10.2 `notifiers/`

通知渠道也是横向增长的实现集合，应继续独立成目录：

- `common.py` 只放多个通知渠道确实共享的消息格式。
- `dingtalk.py` 和 `feishu.py` 分别处理协议、签名和请求。
- 渠道间不应通过导入另一个具体通知器复用异常类型。

当前 `feishu.py` 从 `dingtalk.py` 导入 `NotificationError`，整理时应把该异常移动到
`notifiers/common.py`，消除具体渠道之间的横向依赖。

## 11. 目标依赖方向

最终依赖应大致保持单向：

```text
sites.toml
    │
    ▼
catalog ──────► config
                   │
                   ▼
contracts ◄── checkers ──► http_client
    ▲              │             │
    │              └────────► security
    │
    ├──── notifiers ────────► http_client
    │          │
    │          └────────────► security
    │
state ◄──────── runner ─────► security
                    ▲
                    │
                   cli
```

必须避免：

- `catalog.py` 导入具体 Checker。
- `contracts.py` 导入配置或具体实现。
- `state.py` 导入 Runner。
- Checker 相互导入。
- 通知渠道相互导入。
- `http_client.py` 知道具体站点或通知渠道。

## 12. 测试文件整理

目标测试结构：

```text
tests/
├─ test_catalog.py
├─ test_config.py
├─ test_contracts.py
├─ test_http_client.py
├─ test_runner.py
├─ test_state.py
├─ test_security.py
├─ test_checkers.py
├─ test_notifiers.py
├─ test_cli.py
├─ test_qinglong_entry.py
├─ test_site_sync.py
└─ test_workflows.py
```

调整内容：

- `test_site_catalog.py` 重命名为 `test_catalog.py`。
- `test_http.py` 重命名为 `test_http_client.py`。
- 模型和接口的直接测试集中到 `test_contracts.py`。
- `registry.py` 的重复检查测试迁移到 `test_runner.py`。
- 不为了文件名变化重写行为测试；优先保持断言内容不变。
- 测试不得依赖旧模块的兼容转发文件。

## 13. 实施步骤

### 阶段 A：建立新契约模块

1. 新增 `contracts.py`，迁移模型、枚举和抽象接口。
2. 更新一个依赖层次最低的模块导入并运行测试。
3. 分批更新 Checker、通知器、状态、Runner、CLI 和测试导入。
4. 确认无旧导入后删除 `models.py` 与 `interfaces.py`。

### 阶段 B：删除注册层

1. 将 Checker 重复检查移动到 Runner 构造过程。
2. 将通知渠道重复检查放到通知构建或 Runner 构造过程。
3. 迁移重复检查测试。
4. 删除 `registry.py`。

### 阶段 C：重命名清单和 HTTP 模块

1. 使用 `git mv` 将 `site_catalog.py` 改为 `catalog.py`。
2. 使用 `git mv` 将 `http.py` 改为 `http_client.py`。
3. 更新全部生产、青龙、工具和测试导入。
4. 重命名对应测试文件。
5. 使用 `rg` 确认旧模块名不再出现。

### 阶段 D：清理通知器依赖

1. 将 `NotificationError` 移到 `notifiers/common.py`。
2. 钉钉和飞书都从公共模块导入。
3. 确认两个具体渠道不再相互依赖。

### 阶段 E：文档与最终清理

1. 更新 `docs/architecture.md` 的目录和依赖说明。
2. 更新 `docs/adding-a-site.md` 的导入示例。
3. 更新 `docs/extension-strategy.md` 的模块边界决策。
4. 删除空文件、无用导出和过时注释。
5. 确认没有新建 `utils.py` 或无实际成员的目录。

## 14. 建议提交边界

为了便于审查和回退，建议至少拆为以下提交：

1. `refactor: consolidate runtime contracts`
2. `refactor: remove redundant component registry`
3. `refactor: clarify catalog and http module names`
4. `refactor: decouple notifier implementations`
5. `docs: update simplified module architecture`

如果项目不需要如此细的历史，至少保持“站点清单重构”和“模块路径整理”为两个独立提交。

## 15. 兼容要求

模块整理后必须保持：

- CLI 命令和退出码不变。
- Actions 与青龙调用方式不变。
- 站点配置和环境变量名不变。
- Checker 成功、已完成、失败和可重试语义不变。
- 多账号执行顺序和隔离行为不变。
- 通知模式和渠道隔离行为不变。
- 状态文件格式和匿名账号键算法不变。
- HTTP 安全约束和重试行为不变。
- 日志脱敏行为不变。

内部 Python 导入路径允许改变，因为本项目当前未承诺稳定的第三方库 API。

## 16. 验收标准

实施后执行：

```powershell
python tools/sync_sites.py --check
python -m ruff check .
python -m pytest --cov=checkin_tools --cov-report=term-missing
```

并使用搜索确认：

```powershell
rg "checkin_tools\.(models|interfaces|registry|site_catalog|http)(\.|\s|$)" .
rg "from checkin_tools\.notifiers\.(dingtalk|feishu) import NotificationError" .
```

必须满足：

- 旧模块导入不存在。
- `registry.py`、`models.py` 和 `interfaces.py` 已删除。
- `contracts.py` 不依赖具体实现。
- 具体通知渠道不相互导入。
- 同步文件无漂移。
- Ruff、全量测试和覆盖率阈值通过。
- 测试数量减少只能来自确实重复的注册层测试，不能删除业务边界覆盖。
- 没有执行真实签到或发送通知。

## 17. 后续扩展边界

只有在实际增加 Shell 或 JavaScript 执行需求后，才评估新增：

```text
executors/
├─ python.py
├─ javascript.py
└─ shell.py
```

届时必须先定义统一输入、JSON 结果、超时、退出码、日志脱敏和多账号隔离协议。仅因为存在多种文件
后缀，不足以提前创建执行器目录或抽象层。

本计划完成后的原则是：顶层文件代表稳定的单一核心职责，子目录只用于会持续横向增加的一组实现。
