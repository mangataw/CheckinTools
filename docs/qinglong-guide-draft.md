# 青龙使用方法草案（v2，待实现/实测）

> 配套[修订计划](qinglong-compatibility-plan.md)。青龙入口、脚本、模板、一键导入和新通知选项尚未实现。
> 不要在当前 0.1.0 执行拟新增命令。原版本问题已独立修正为 4c3ff93，青龙功能尚未实现。

## 1. 两种独立使用方式

Actions 使用原 CLI/Secrets/Cache/通知，青龙使用独立入口、配置和记录，两者不共享执行结果。
安装青龙不要求关闭 Actions，也不修改它。同账号两边启用可能重复请求/通知，不做跨端去重。

默认时间也独立：Actions 北京时间 09:00/14:00；青龙当地 00:30/08:30，可自定义。
正式版须补齐认证青龙版本、镜像 digest、Python、架构和验证日期，目前不宣称已实测兼容。

## 2. 安装准备

需要已运行的青龙 Linux 环境、Python 3.12+、pip/venv、Git、Bash、HTTPS 证书及相应 IANA 时区数据。
没有青龙时参照[官方部署说明](https://qinglong.online/guide/getting-started/installation-guide)。
数据须持久化；下文是青龙容器内 /ql/data 路径，不是宿主机路径。

~~~bash
python3 --version
python3 -m pip --version
git --version
date
~~~

不默认任何青龙镜像都有兼容 Python；不足时选择认证镜像/解释器，不替换其他任务的系统依赖。
以下仅在兼容版本发布后执行，标签占位符必须替换；已有 repo 时走升级，不覆盖：

~~~bash
git clone --branch <已发布的兼容版本标签> https://github.com/mangataw/CheckinTools.git /ql/data/checkin-tools/repo
bash /ql/data/checkin-tools/repo/deploy/qinglong/install.sh
bash /ql/data/checkin-tools/repo/deploy/qinglong/manage.sh init-config
~~~

install 只创建独立 venv 并安装生产包；init-config 将带注释模板复制到
/ql/data/checkin-tools/config/config.toml，存在时拒绝覆盖。都不签到、不发消息、不创建执行任务。
必须获取完整仓库，不能只订阅一个脚本代替包安装。

## 3. 一份配置文件管理所有任务

默认文件 /ql/data/checkin-tools/config/config.toml；权限建议 0600，不放 repo、不上传 Git。
可用 CTQL_CONFIG 或 --config 指定绝对路径。配置采用 TOML，不是可 source 的 Shell 文件。

以下为拟交付模板示例；任务默认关闭，填写完整后再启用：

~~~toml
schema_version = 1

[runtime]
# local 是青龙实际调度时区；导入时显示解析出的 IANA 名称。
# 无法确定时改为明确值，例如 "Asia/Shanghai"，须与青龙一致。
timezone = "local"
state_dir = "/ql/data/checkin-tools/runtime"
task_timeout_seconds = 900
group_timeout_seconds = 1800

[schedule]
# 默认当地每天 00:30、08:30；每任务可覆盖 cron。
cron = "30 0,8 * * *"

[notify]
# 独立开关：可两者都开、只开一种或都关闭。
on_success = true
on_failure = true
# individual 每任务结束就发；grouped 同计划/同策略集合。
delivery = "individual"
# auto/all/dingtalk/feishu；auto 两者都有时优先钉钉。
channel = "auto"

[notify.dingtalk]
# 成对填写。改用 *_env 引用时删除对应字面量键，即使它为空。
access_token = ""
secret = ""
# access_token_env = "CTQL_DINGTALK_ACCESS_TOKEN"
# secret_env = "CTQL_DINGTALK_SECRET"

[notify.feishu]
webhook = ""
secret = ""
# webhook_env = "CTQL_FEISHU_WEBHOOK"
# secret_env = "CTQL_FEISHU_SECRET"

[logs]
retention_days = 14
max_file_mb = 5
max_total_mb = 100
results_retention_days = 30
results_max_total_mb = 20
# 本项目维护时间，不清理其他任务。
cleanup_cron = "15 3 * * *"

[qinglong]
# 本机回环允许 HTTP，远程面板必须 HTTPS。
base_url = "http://127.0.0.1:5700"
# 仅导入/同步需要，日常签到不需要管理 API 密钥。
client_id_env = "CTQL_CLIENT_ID"
client_secret_env = "CTQL_CLIENT_SECRET"

[[tasks]]
id = "javbus-main"
name = "JavBus 每日登录"
site = "javbus"
enabled = false
# cron = "30 0,8 * * *"
[[tasks.accounts]]
id = "main"
label = "账号A"
cookie = ""
# cookie_env = "CTQL_JAVBUS_MAIN_COOKIE"

[[tasks]]
id = "fuliba-main"
name = "福利吧签到"
site = "fuliba"
enabled = false
[[tasks.accounts]]
id = "main"
label = "账号A"
username = ""
cookie = ""
# username_env = "CTQL_FULIBA_MAIN_USERNAME"
# cookie_env = "CTQL_FULIBA_MAIN_COOKIE"

[[tasks]]
id = "v2ex-main"
name = "V2EX 每日奖励"
site = "v2ex"
enabled = false
# 本任务时间覆盖示例，其他任务不受影响：
# cron = "45 8 * * *"
[[tasks.accounts]]
id = "main"
label = "账号A"
username = ""
# TOML 单引号保留 Cookie 内的双引号，不加 Shell 外层转义。
cookie = ''
# username_env = "CTQL_V2EX_MAIN_USERNAME"
# cookie_env = "CTQL_V2EX_MAIN_COOKIE"

# 可在对应任务区块内添加通知覆盖：
# [tasks.notify]
# on_success = false
# on_failure = true
# delivery = "individual"

# 监控按实际导入入口配置；组 ID 从导入预览获取。
# [monitoring.targets."task:v2ex-main"]
# url_env = "CTQL_V2EX_HEARTBEAT_URL"
~~~

填写规则：

- 每任务一个唯一稳定 ID，每账号也有 ID；显示名/排序可改。换账号身份须换 ID 或显式清理该账号状态。
- 多账号添加多个 tasks.accounts，不再要求多行用户名/Cookie 配对。
- 字面量字段与 *_env 互斥，改引用时先删字面量键；引用变量建议 CTQL_ 前缀。
- 所有参数可直接在文件内填；选择引用的秘密才需填青龙环境变量面板，不维护两份任务配置。
- 面板变量值是原始内容，不包含 export 或 dotenv 外层引号；TOML 字面量遵守 TOML 引号规则。
- 没有 .env 或原 Actions 变量自动回退；原变量只有被明确引用才读取，不能误把多账号值当单账号。
- 禁用任务可保留空凭据，启用必须完整。钉钉 token/secret、飞书 webhook/secret 成对。
- 通知开启但无可用渠道时预检报错；不需要业务通知可将两个开关都关掉。
- 用户配置不随仓库更新覆盖；保管面板权限及配置/备份，不能当作多租户安全隔离。

Cookie 获取继续参考 [JavBus](javbus.md)、[福利吧](fuliba.md)、[V2EX](v2ex.md)。

## 4. 一键导入任务

### 4.1 一次性授权

在青龙系统设置的应用设置创建专用应用，开放所需定时任务模块权限，获得 client_id/client_secret。
具体操作参考[官方 API 准备工作](https://qinglong.online/api/preparation)。
填写配置引用的 CTQL_CLIENT_ID/CTQL_CLIENT_SECRET，或改为对应字面量字段；不把秘密放进命令行。

如果值只在面板环境变量中，导入须在能注入变量的青龙运行环境执行。
普通宿主机终端/docker exec 不保证获得面板变量。
正式教程会提供认证版本的一次性引导执行操作；最多需要创建一个导入引导任务，不需要逐个创建业务任务。

### 4.2 预检、预览和批量导入

拟新增：

~~~bash
bash /ql/data/checkin-tools/repo/deploy/qinglong/manage.sh doctor
bash /ql/data/checkin-tools/repo/deploy/qinglong/manage.sh import-tasks --dry-run
bash /ql/data/checkin-tools/repo/deploy/qinglong/manage.sh import-tasks --yes
~~~

doctor 校验环境/配置/实际时区，不签到；预览显示名称、ID、分组、cron、时区、下次时间和创建/更新/禁用差异。
dry-run 可读 API 获取差异，但不创建任务、不发业务通知。
yes 一次创建所有配置启用的业务任务及维护任务；首次业务任务默认禁用，防止配置还未验证就执行。
具体任务操作使用[公开任务 API](https://qinglong.online/api/crontab)，不用手工复制每项命令。

验证后统一启用：

~~~bash
bash /ql/data/checkin-tools/repo/deploy/qinglong/manage.sh import-tasks --yes --enable
~~~

enable 表示授权自动执行，到计划时间就会真实签到。导入本身不立即签到。
重复导入不重复创建；配置移除的受管任务默认禁用不删日志；其他青龙任务不受影响。
更新保留启用状态，分组变更会安全切换旧新任务；部分失败给回滚结果，不应盲目再建一套。
面板手改与配置冲突会提示，不静默覆盖。

## 5. 自定义时间与手动验证

全局默认 30 0,8 * * *；例如给 V2EX 写 cron = "45 8 * * *"，它只在当地 08:45 执行，其他任务不变。
改时间后重导并核对面板下次执行预览。
local 解析不明/与面板时区不匹配时先修配置，工具不会擅自改整个青龙实例时区。

站点服务日不同于调度日期：北京时间 00:30、08:30 对 V2EX 是两个不同 UTC 日。
DST 地区的重复/跳过时刻按认证版本文档说明。

拟新增测试命令（会真实发消息/签到，不是 dry-run）：

~~~bash
bash /ql/data/checkin-tools/repo/deploy/qinglong/manage.sh notify-test --channel dingtalk
bash /ql/data/checkin-tools/repo/deploy/qinglong/manage.sh run --task v2ex-main --no-heartbeat
~~~

选择已配置渠道/启用任务测试，核对状态、通知和日志后再启用定时。
手动运行单独标 manual，不混入其他定时集合。需要忽略状态排障时显式加 --force，仍使用锁，可能再次访问站点。
同账号 Cookie 更新下轮读取；任务/账号身份和分组变化遵守配置同步规则。

## 6. 两维通知配置

### 6.1 成功/失败是否发

| on_success | on_failure | 效果 |
| --- | --- | --- |
| true | true | 成功和失败都通知（默认） |
| false | true | 只失败 |
| true | false | 只成功 |
| false | false | 不发业务通知，保留结果/日志 |

部分账号失败按任务失败；已签到/本服务日跳过属成功类，但消息不把跳过称为本次签到成功。
不影响 Actions 的通知，也不关闭独立漏执行监控。

### 6.2 集合/分别发送

- individual：逻辑任务结束就发一条，包含该任务全部账号；不同时间/耗时优先选择。
- grouped：相同时区、规范化 cron、通知渠道/策略的任务成组，逐项隔离执行，全部结束发一份。
- 不同时间分开；00:30 不等 08:30；不同 cron 即使偶然同分钟也不跨组汇总。
- 任务通知覆盖不同自动拆组；组超时列已完成、失败和未执行项，不当作全成功。
- 只失败的集合消息只展开失败任务，保留总体计数；只成功同理，筛选后无结果不发。
- 集合需等本批结束；想尽快得知失败选分别模式，不额外发重复失败通知。
- 修改 delivery 后重新导入，导入器重组并处理旧任务，防止双重运行。

### 6.3 结果示例（虚构数据）

~~~text
[CheckinTools · 青龙] V2EX 每日奖励：成功
计划：2026-09-06 08:30 +08:00
实际：08:30:03–08:30:09，耗时 6 秒
账号：1；成功 1 / 已签到 0 / 跳过 0 / 失败 0
账号A：领取 25 铜币；余额 1,025 铜币；连续 7 天
运行编号：ql-20260906-083003-xxxx
~~~

~~~text
[CheckinTools · 青龙] 00:30 批次：部分失败
任务：3；成功 2 / 失败 1；耗时 18 秒
JavBus / 账号A：今日已完成
福利吧 / 账号A：登录状态无效，请更新对应 Cookie
V2EX / 账号A：本服务日已成功，本次跳过
运行编号：ql-20260906-003000-yyyy
~~~

仅展示站点实际返回且确认的收益/余额/连续天数，无数据则省略，不推算。
超长消息分页并保留失败信息/运行编号。
业务状态与投递状态分开：通知失败不抹掉已完成签到状态，但运行日志/退出码会反映投递失败。
别名不要使用真实用户名；不发送 Cookie、完整配置或原始网页。

## 7. 日志保存与过期清理

自有 runtime/logs 是日志，runtime/records 是结构化结果，runtime/state 是去重状态。
默认日志 14 天、单文件 5 MiB、目录 100 MiB；结果 30 天、目录 20 MiB。
满足过期或容量限制时删最旧已完成文件，活动文件保留并滚动。

一键导入同时创建当地 03:15 的项目维护任务，普通执行也做轻量清理。可预览：

~~~bash
bash /ql/data/checkin-tools/repo/deploy/qinglong/manage.sh cleanup --dry-run
~~~

删除日志不可恢复，需要长期保存先导出脱敏材料。
不清理 state/config/backups/锁/导入清单，不跟随外部链接，不动其他项目文件。
青龙面板捕获的 stdout 日志另由青龙管理，需要查看其日志保留设置；项目不改影响其他任务的全局规则。
维护正常完成不刷屏，清理失败按维护失败告警。

| 退出码 | 含义 |
| --- | --- |
| 0 | 成功/已完成/状态跳过，或管理操作成功 |
| 1 | 业务、投递、超时、必要落盘等失败，查看分类 |
| 2 | 参数、配置或环境无效 |
| 3 | 同任务已有实例持锁，本次未执行 |

面板“已结束”不等于业务成功，结合运行结果、退出码和投递状态判断。

## 8. 未执行告警

失败通知只能覆盖程序运行且能发消息的场景；青龙停机/脚本没启动需要独立 Healthchecks 兼容监控。
分别模式每任务独立监控，集合模式每实际组独立监控；ID 从导入预览取，不自行猜测。

1. 采用导入清单的 cron 和具体时区，默认当地 00:30/08:30。
2. 宽限大于执行上限和延迟：单任务默认 15 分钟可配 30 分钟，组默认 30 分钟可配 45 分钟。
3. 外部服务单独配置/测试告警渠道，不会继承项目机器人参数。
4. 将基础 ping URL 配置为对应目标字面量或 url_env，不附加 start/fail。
5. 正常运行确认开始/成功；用 mock 测试任务暂停演练漏执行，勿频繁真实签到。

示例：

~~~toml
[monitoring.targets."task:v2ex-main"]
url_env = "CTQL_V2EX_HEARTBEAT_URL"
~~~

协议见[开始/结束监测](https://healthchecks.io/docs/measuring_script_run_time/)和[失败信号](https://healthchecks.io/docs/signaling_failures/)。
同一个 URL 不给不同 cron 或 Actions/青龙共用，避免相互掩盖漏执行。
修改 cron/分组后同步外部监控，导入器提示但不代操作外部服务。
未配心跳无额外联网，心跳故障不阻断签到；URL 是密钥，不能公开。
同机监控不能覆盖整机停电，须独立服务/设备。

## 9. 维护、更新、回滚

- 同身份 Cookie 更新下轮生效；排序/显示名改变不改变稳定 ID。
- 更换账号身份换 ID，或停任务后重置对应账号状态；不能把别人的旧成功记录沿用。
- 增删任务、时间、通知组织变化：doctor → 导入预览 → 一键同步；核对启用状态。
- 文件是唯一任务配置源，面板命令/cron 是生成结果，不建议另改一份。
- 初始化/升级不覆盖用户文件；schema 升级先备份再迁移。
- 不每次签到前 git pull/pip install。升级先禁用项目任务并等结束，记录 revision/依赖、备份 config/runtime。
- 检查用户源码改动后更新明确版本、重装、doctor、同步清单、手动验证，再恢复启用。
- 回滚恢复旧代码/匹配依赖/schema/任务清单，核对本项目映射，不操作其他任务；API 部分失败按报告修复。
- 卸载先停本项目任务、保留必要备份，再移除精确项目目录，不删 /ql/data。
- 青龙方式升级/卸载不影响原 Actions/本地 CLI，两端运行安排由用户决定。

## 10. 常见问题与反馈

| 问题 | 检查 |
| --- | --- |
| 导入授权失败 | 应用模块权限及密钥读取环境，不把 secret 放命令 |
| 同名/重复任务 | 项目标记和导入清单，不能按名字覆盖外部任务 |
| 时间不对 | local 解析是否真实青龙时区，是否重导 |
| V2EX 凌晨/早上都执行 | 是否跨 UTC 服务日，不一定是去重错误 |
| 没有成功通知 | on_success、任务覆盖、渠道，跳过在青龙也由成功开关控制 |
| 集合消息晚 | 等本组结束，需要及时则 individual |
| 参数修改未生效 | 秘密下轮读，调度/分组要重导，别维护面板/文件两套 |
| Cookie 引号问题 | TOML 与环境值规则不同，保留 Cookie 自身字符 |
| 日志仍占空间 | 区分自有日志/面板日志，检查各自保留和维护任务 |
| 锁占用 | 等正在执行实例，不删除持锁文件绕过 |
| 状态/权限错误 | 停任务并备份对应文件，修复精确对象，不清空整个数据目录 |
| 模块/venv 缺失 | 完整仓库重新安装、检查 3.12+ 及解释器路径 |
| 语法错误没通知 | 可能无法解析渠道，查看面板日志/外部监控 |

反馈仅提供 revision、青龙/镜像/Python/架构、任务 ID、时区、退出码及脱敏日志。
不提供 Cookie、真实用户名、客户端密钥、完整配置导出、Webhook/心跳 URL。

P0 已独立提交为 4c3ff93；正式发布前仍须完成青龙功能、兼容测试与认证青龙实测。本文件目前仅供评审。
