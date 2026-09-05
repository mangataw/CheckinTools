# 青龙 Docker 使用教程

本项目按青龙仓库订阅的常见目录组织任务：`qinglong/DefaultTasks` 中所有相关文件都使用
`checkin_task_` 前缀。订阅只需填写这个前缀，不必逐个列出脚本。

订阅完成后，「定时任务」应出现三个独立任务：JavBus、福利吧、V2EX。三个任务默认都在
青龙容器当地时间每天 `00:30` 和 `08:30` 运行。公共文件
`checkin_task_base.py` 没有 cron 元数据，因此不会生成第四个任务。
`checkin_task_setup.py` 也不是定时任务，它只在订阅完成后初始化配置并安装依赖。

## 1. 创建订阅

在青龙「订阅管理 → 新建订阅」最上面的名称输入框粘贴：

```text
ql repo https://github.com/mangataw/CheckinTools.git "checkin_task_"
```

这条命令用于自动展开仓库地址和白名单。新版青龙仍需在图形界面补充名称、订阅更新计划
和执行后命令：

| 输入框 | 填写值 |
| --- | --- |
| 名称 | `CheckinTools` |
| 类型 | `公开仓库` |
| 链接 | `https://github.com/mangataw/CheckinTools.git` |
| 分支 | `main` |
| 定时类型 | `crontab` |
| 定时规则 | `15 3 * * *` |
| 白名单 | `checkin_task_` |
| 黑名单 | 留空 |
| 依赖文件 | 留空 |
| 文件后缀 | `py` |
| 执行后 | `python3 /ql/data/repo/mangataw_CheckinTools_main/qinglong/DefaultTasks/checkin_task_setup.py` |
| 自动添加任务 | 开启 |
| 自动删除任务 | 开启 |

「定时规则」是更新订阅的时间，不是签到时间。建议每天 03:15 更新仓库。签到时间由三个
入口文件中的 `30 0,8 * * *` 决定。

「执行后」填写一行：

```sh
python3 /ql/data/repo/mangataw_CheckinTools_main/qinglong/DefaultTasks/checkin_task_setup.py
```

`mangataw_CheckinTools_main` 是通常生成的订阅唯一值。如果面板显示的「唯一值」不同，请只
替换命令中的这段目录名。保存后手动运行一次订阅。初始化脚本会完成两件事：

1. 仅在缺失时复制 `/ql/data/config/checkin-tools.env`。
2. 使用当前 `python3` 执行 `pip install -e`，自动安装项目及 `pyproject.toml` 声明的依赖。

## 2. 配置文件为何不会被更新覆盖

仓库中的 `qinglong/checkin-tools.env` 只是公开模板，每次更新订阅时可以正常刷新。
初始化脚本使用排他创建，只在 `/ql/data/config/checkin-tools.env` 不存在时复制。因此你在
青龙「配置文件」页面填写的 Cookie 和通知密钥不会被后续订阅覆盖。

任务本身不会创建或改写配置文件。首次订阅成功后即可在青龙「配置文件」中打开
`checkin-tools.env`，修改后直接运行三个签到任务。

## 3. 黑白名单与目录

- 白名单只填 `checkin_task_`，它会选中三个任务入口、公共运行文件和初始化文件。
- 黑名单留空。两个公共文件都没有 `cron`/`new Env`，青龙不会把它们注册成任务。
- 依赖文件留空。公共文件已经被同一个白名单选中，无需重复声明。
- 文件后缀填 `py`，让青龙扫描 Python 任务。

这种形式参考 BiliBiliToolPro 的 `qinglong/DefaultTasks` 和统一任务前缀做法，同时保留
CheckinTools 现有 Python 包和三个站点的独立任务。

## 4. 编辑账号配置

没有使用的站点保持为空，并在「定时任务」中禁用对应任务。主要变量如下：

| 变量 | 用途 |
| --- | --- |
| `JAVBUS_COOKIES` | JavBus Cookie |
| `FULIBA_USERNAMES` / `FULIBA_COOKIES` | 福利吧用户名和 Cookie |
| `V2EX_USERNAMES` / `V2EX_COOKIES` | V2EX 用户名和 Cookie |
| `DINGTALK_ACCESS_TOKEN` / `DINGTALK_SECRET` | 可选钉钉通知，成对填写 |
| `FEISHU_WEBHOOK` / `FEISHU_SECRET` | 可选飞书通知，成对填写 |

多账号使用字面量 `\n` 分隔，用户名和 Cookie 必须逐项对应：

```dotenv
FULIBA_USERNAMES='user1\nuser2'
FULIBA_COOKIES='cookie1\ncookie2'
```

配置文件是青龙任务的参数来源，不需要在面板中逐个创建环境变量。

## 5. Python 依赖

订阅执行后会自动安装项目声明的依赖，目前包括：

```text
beautifulsoup4
python-dotenv
requests
```

通常不再需要在青龙依赖管理中逐个添加。青龙 Docker 内的 Python 需要 3.12 或更高版本，
可在容器内运行 `python3 --version` 检查。自动安装失败时，订阅日志会保留完整 pip 错误。

## 6. 运行、状态与迁移

三个任务分别保存状态：

```text
/ql/data/checkin-tools/javbus-state.json
/ql/data/checkin-tools/fuliba-state.json
/ql/data/checkin-tools/v2ex-state.json
```

每天 00:30 首次执行后，08:30 会重试失败账号并跳过已成功账号。V2EX 按 UTC 服务日判断，
JavBus 和福利吧按北京时间判断。

如果旧订阅中只有 `CheckinTools 每日签到`，用第 1 节的参数修改并重新运行订阅。确认三个
新任务出现后删除或禁用旧任务。已有的 `/ql/data/config/checkin-tools.env` 会被保留。

常见问题：

- 仍只有一个任务：检查白名单是否已经改为 `checkin_task_`，并开启自动添加任务。
- 没有配置文件：检查订阅日志中的执行后命令和订阅唯一值目录。
- 提示缺包：重新运行订阅并检查“执行后”的 pip 日志。
- 某站点提示未配置：填写该站点参数，或禁用该站点任务。
- 时间不符：检查青龙 Docker 的时区；任务 cron 使用容器当地时间。

获取 Cookie 参阅 [JavBus](javbus.md)、[福利吧](fuliba.md) 和 [V2EX](v2ex.md)。
