# 青龙 Docker 使用教程

本项目按青龙仓库订阅的常见目录组织任务。各站点入口使用 `checkin_task_` 前缀，公共
运行与初始化文件使用 `checkin_` 前缀，避免青龙把公共文件注册成定时任务。

订阅完成后，「定时任务」应为每个内置站点出现一个独立任务。各任务默认都在
青龙容器当地时间每天 `00:30` 和 `08:30` 运行。公共文件
`checkin_base.py` 由各任务共同调用。`checkin_setup.py` 只在订阅完成后初始化配置并安装
依赖；两者都不匹配任务白名单。

## 1. 创建订阅

在青龙「订阅管理 → 新建订阅」最上面的名称输入框粘贴：

```text
ql repo "https://github.com/mangataw/CheckinTools.git" "checkin_task_[a-z0-9_]+[.]py" "" "checkin_base.py|checkin_setup.py|src" "main" "py"
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
| 白名单 | 与上方命令的第 2 个参数相同 |
| 黑名单 | 留空 |
| 依赖文件 | 与上方命令的第 4 个参数相同 |
| 文件后缀 | `py` |
| 执行后 | `python3 /ql/data/repo/mangataw_CheckinTools_main/qinglong/DefaultTasks/checkin_setup.py` |
| 自动添加任务 | 开启 |
| 自动删除任务 | 开启 |

「定时规则」是更新订阅的时间，不是签到时间。建议每天 03:15 更新仓库。签到时间由各站点
入口文件中的 cron 声明决定。

「执行后」填写一行：

```sh
python3 /ql/data/repo/mangataw_CheckinTools_main/qinglong/DefaultTasks/checkin_setup.py
```

`mangataw_CheckinTools_main` 是通常生成的订阅唯一值。如果面板显示的「唯一值」不同，请只
替换命令中的这段目录名。保存后手动运行一次订阅。初始化脚本会完成两件事：

1. 缺失时创建 `/ql/data/config/checkin-tools.env`；文件已存在时只补充新版模板中的缺失字段。
2. 使用当前 `python3` 执行 `pip install -e`，自动安装项目及 `pyproject.toml` 声明的依赖。

## 2. 配置文件如何安全升级

仓库中的 `qinglong/checkin-tools.env` 只是公开模板，每次更新订阅时可以正常刷新。
初始化脚本使用排他创建，只在 `/ql/data/config/checkin-tools.env` 不存在时复制完整模板。
文件已经存在时，它会比较配置键，并把新版模板中缺少的赋值追加到文件末尾。原文件内容会原样
保留，已有 Cookie、通知密钥、注释和自定义值不会被覆盖。重复执行更新不会重复添加字段。

自动升级只处理新增字段。若以后需要删除或重命名配置项，项目会在升级说明中给出人工迁移步骤。
订阅更新后如果日志显示“已补充配置字段”，请打开配置文件填写其中新增的空值；未使用的站点可
继续留空。

签到任务本身不会创建或改写配置文件，只有订阅的“执行后”初始化脚本负责创建和补充字段。
首次订阅成功后即可在青龙「配置文件」中打开
`checkin-tools.env`，修改后直接运行相应签到任务。

## 3. 黑白名单与目录

- 白名单匹配小写字母、数字或下划线组成的 `checkin_task_<站点>.py`，因此只会创建站点入口
  对应的定时任务。
- 黑名单留空，因为白名单已经排除了公共文件。
- 依赖文件填写 `checkin_base.py|checkin_setup.py|src`，让各任务和执行后钩子仍能使用公共
  代码及原项目源码。
- 文件后缀填 `py`，让青龙扫描 Python 任务。

这种形式参考 BiliBiliToolPro 的 `qinglong/DefaultTasks` 和统一任务前缀做法，同时保留
CheckinTools 现有 Python 包和各站点的独立任务。

## 4. 编辑账号配置

没有使用的站点保持为空，并在「定时任务」中禁用对应任务。主要变量如下：

<!-- BEGIN GENERATED: qinglong-site-config -->
| 变量 | 用途 |
| --- | --- |
| `JAVBUS_COOKIES` | JavBus，每行一个账号 Cookie |
| `FULIBA_USERNAMES` | 福利吧用户名，每行一个 |
| `FULIBA_COOKIES` | 福利吧 Cookie，与用户名按行对应 |
| `V2EX_USERNAMES` | V2EX 用户名，每行一个 |
| `V2EX_COOKIES` | V2EX 完整 Cookie，与用户名按行对应 |
| `DINGTALK_ACCESS_TOKEN` / `DINGTALK_SECRET` | 可选钉钉通知，成对填写 |
| `FEISHU_WEBHOOK` / `FEISHU_SECRET` | 可选飞书通知，成对填写 |
<!-- END GENERATED: qinglong-site-config -->

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

通常不再需要在青龙依赖管理中逐个添加。青龙 Docker 内的 Python 需要 3.10 或更高版本，
可在容器内运行 `python3 --version` 检查。自动安装失败时，订阅日志会保留完整 pip 错误。

## 6. 运行、状态与迁移

各任务分别保存状态：

<!-- BEGIN GENERATED: qinglong-state-files -->
```text
/ql/data/checkin-tools/javbus-state.json
/ql/data/checkin-tools/fuliba-state.json
/ql/data/checkin-tools/v2ex-state.json
```
<!-- END GENERATED: qinglong-state-files -->

每天 00:30 首次执行后，08:30 会重试签到失败的账号，并跳过当天已经签到成功或已经签到的
账号。各站点都按青龙容器本地日期保存状态，因此被跳过的账号不会重复发送通知。

通知发送失败会使当次任务返回失败，方便在日志中发现问题，但不会撤销已成功的签到状态，
也不会让 08:30 的任务专门重试通知。签到失败和通知失败是两种独立状态。

如果旧订阅中只有 `CheckinTools 每日签到`，用第 1 节的参数修改并重新运行订阅。确认各站点
新任务出现后删除或禁用旧任务。已有的 `/ql/data/config/checkin-tools.env` 会被保留。

常见问题：

- 出现 base/setup 任务：使用第 1 节的精确白名单，重新运行订阅；若旧任务未被自动删除，
  在定时任务中手动删除这两个旧条目。
- 没有配置文件：检查订阅日志中的执行后命令和订阅唯一值目录。
- 提示缺包：重新运行订阅并检查“执行后”的 pip 日志。
- 某站点提示未配置：填写该站点参数，或禁用该站点任务。
- 时间不符：检查青龙 Docker 的时区；任务 cron 使用容器当地时间。

各站点的 Cookie 获取方法参阅 README 中自动生成的站点文档列表。
