# 青龙 Docker 使用教程

本项目采用青龙原生仓库订阅方式。顶层脚本 `qinglong_checkin.py` 使用与
`mangataw/fubasing` 相同的文件头元数据：

```python
"""
cron: 30 0,8 * * *
new Env('CheckinTools 每日签到');
"""
```

青龙拉取仓库后会据此创建每天 00:30、08:30 执行的任务，不需要申请应用密钥，
也不需要调用青龙 API。运行日志和任务启停均由青龙面板管理。

## 1. 添加仓库订阅

打开青龙面板的「订阅管理」，新建公开仓库订阅：

| 配置项 | 内容 |
| --- | --- |
| 名称 | `CheckinTools` |
| 仓库地址 | `https://github.com/mangataw/CheckinTools.git` |
| 分支 | `main` |
| 白名单 | `qinglong_checkin.py` |
| 依赖文件 | `src` |
| 文件后缀 | `py` |
| 订阅定时 | 例如 `15 3 * * *`，只用于更新仓库 |

不同青龙版本的字段名称可能略有差异。关键点是拉取 `qinglong_checkin.py`，同时保留
`src/checkin_tools`。如果你的版本默认拉取完整仓库，依赖文件可以留空。

保存后手动运行一次订阅。在「定时任务」中应自动出现 `CheckinTools 每日签到`。
先保持该任务禁用，手动运行一次。首次运行会生成完整配置模板并提示路径，不会签到。

旧版青龙也可以在定时任务中使用拉库命令：

```bash
ql repo https://github.com/mangataw/CheckinTools.git "qinglong_checkin.py" "" "src" "main" "py"
```

参数格式随青龙版本可能变化，面板的「订阅管理」优先。

## 2. 安装 Python 依赖

在青龙「依赖管理 → Python3」中添加：

```text
beautifulsoup4
python-dotenv
requests
```

青龙 Docker 内的 Python 必须为 3.12 或更高版本。可在容器终端检查：

```bash
python3 --version
```

脚本直接使用青龙容器内的 Python 和依赖，不创建额外 venv，也不修改系统包。

## 3. 编辑一个集中配置文件

首次运行会创建：

```text
/ql/data/config/checkin-tools.env
```

文件带有全部参数、中文分区和填写示例，已存在时绝不覆盖。多数版本可以在青龙
「配置文件」页面直接打开；如果面板没有列出自定义 `.env` 文件，可进入容器编辑该路径。
文件位于 Docker 持久化的 `/ql/data` 中，仓库更新和容器重建不会覆盖。

账号参数：

| 变量 | 用途 |
| --- | --- |
| `JAVBUS_COOKIES` | JavBus Cookie，每行一个账号 |
| `FULIBA_USERNAMES` | 福利吧用户名，每行一个 |
| `FULIBA_COOKIES` | 福利吧 Cookie，与用户名逐行对应 |
| `V2EX_USERNAMES` | V2EX 用户名，每行一个 |
| `V2EX_COOKIES` | V2EX Cookie，与用户名逐行对应 |

通知参数：

| 变量 | 用途 |
| --- | --- |
| `DINGTALK_ACCESS_TOKEN` / `DINGTALK_SECRET` | 钉钉机器人，必须成对 |
| `FEISHU_WEBHOOK` / `FEISHU_SECRET` | 飞书机器人，必须成对 |
| `CHECKIN_NOTIFY_CHANNEL` | `auto`、`all`、`dingtalk`、`feishu` |
| `CHECKIN_NOTIFY_MODE` | `summary` 或 `individual` |

多账号在同一个值中使用字面量 `\n` 分隔，例如：

```dotenv
FULIBA_USERNAMES='user1\nuser2'
FULIBA_COOKIES='cookie1\ncookie2'
```

用户名与 Cookie 必须逐行对应。Cookie 建议使用单引号，避免其中的双引号和符号被改变。
文件存在后以文件内容为准，不再混合读取青龙面板环境变量或仓库 `.env`，避免两套配置冲突。
如需改路径，只需在面板设置一个 `CHECKIN_QINGLONG_CONFIG=/绝对路径/config.env`。
Cookie、用户名、Webhook 和密钥不要写进仓库或任务命令。

## 4. 运行与状态

手动运行 `CheckinTools 每日签到`，确认日志、签到结果和通知，再启用定时任务。

脚本依次执行已配置的站点，一个站点失败不会阻止后续站点。状态文件存放在：

```text
/ql/data/checkin-tools/javbus-state.json
/ql/data/checkin-tools/fuliba-state.json
/ql/data/checkin-tools/v2ex-state.json
```

`/ql/data` 是青龙 Docker 的持久化目录。可以通过
`CHECKIN_QINGLONG_DATA_DIR` 改为另一个绝对路径。
脚本使用 Linux 文件锁避免同一任务重叠运行，锁冲突退出码为 3。

V2EX 按 UTC 日期保存状态，JavBus 和福利吧按北京时间保存状态。因此北京时间
00:30 和 08:30 对 V2EX 属于两个不同服务日，不会被错误去重。

| 退出码 | 含义 |
| --- | --- |
| 0 | 所有已配置站点成功、已签到或状态跳过 |
| 1 | 至少一个站点签到或通知失败 |
| 2 | 配置、依赖、目录或运行环境无效 |
| 3 | 上一次 CheckinTools 青龙任务仍在运行 |

## 5. 自定义执行时间

默认时间来自脚本头部的 `30 0,8 * * *`。青龙创建任务后，可以直接在面板修改该任务的
cron。再次运行仓库订阅时，部分青龙版本可能按脚本元数据恢复默认时间；如需长期使用
其他时间，可 Fork 仓库并修改 `qinglong_checkin.py` 顶部的 cron。

仓库订阅自己的更新时间与签到时间是两件事。订阅任务只负责拉取更新，签到任务才访问站点。

## 6. 更新和排障

更新由青龙订阅任务完成。更新后先手动运行签到任务，确认再保持定时启用。

- 提示缺少 `src`：订阅没有保留源码目录，把 `src` 加入依赖文件或改为拉取完整仓库。
- `ModuleNotFoundError`：在 Python3 依赖管理安装上面的三个包。
- Python 版本错误：当前项目要求 Python 3.12+，需要使用兼容的青龙镜像或解释器。
- 没有生成任务：检查订阅白名单、py 文件后缀，以及脚本是否完整拉取。
- 没有账号：编辑 `/ql/data/config/checkin-tools.env`，用户名与 Cookie 行数必须一致。
- 配置文件没有显示：从容器终端编辑，或用 `CHECKIN_QINGLONG_CONFIG` 指向面板可编辑的文件。
- 状态损坏：先备份对应站点状态文件，再删除该单个文件重建；不要清空整个 `/ql/data`。
- 时间不对：检查青龙容器和面板时区；脚本不修改 Docker 或青龙全局时区。

获取 Cookie 参阅 [JavBus](javbus.md)、[福利吧](fuliba.md) 和 [V2EX](v2ex.md)。
