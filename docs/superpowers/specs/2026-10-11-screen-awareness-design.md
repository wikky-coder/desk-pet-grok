# 桌宠读屏幕（屏幕感知）设计

状态：已由用户批准（2026-10-11）。目标：让小 Grok 能知道主人在用什么软件，必要时「看」一眼屏幕并用猫娘口吻短评，同时把额度、隐私、打扰控制到最低。

## 原则
- 默认全部关闭；右键菜单「屏幕感知」子菜单里逐项打开。开启期间屏幕上有小标记「👀 她在看」。
- 不抢焦点、置顶行为不变（标记窗口与气泡同款：Tool + WindowDoesNotAcceptFocus + ShowWithoutActivating）。
- Key 只从环境变量 `XAI_API_KEY` 读取（沿用 `secrets.get_api_key()` 的既有行为，本功能不写入任何 Key）。
- 截图只在内存里使用：不写日志，不入聊天历史，不发给除 xAI 接口以外的任何地方。窗口标题只用于本地分类/黑名单，**不会**发给接口。
- 她的台词：自称「本喵」偶尔「Wiki」，称用户「主人」，每句以「喵」结尾（`ensure_meow`）。

## 两档
### 档1：读前台软件名 + 窗口标题（不花额度）
- 软件名用 `lsappinfo`（无需权限）；窗口标题、是否全屏、是否在密码框用辅助功能接口（已有权限，缺失则只用软件名）。
- 按软件分类：code / terminal / video / browser / chat / doc / design / game / other。
- 切换软件时才可能说话：code、terminal、video、design、game 保持安静（code 偶尔极低概率），browser、chat、doc 有各自台词；全局最短间隔 10 分钟、同类别 30 分钟；安静模式/聊天框开着/气泡关闭时不说。

### 档2：截屏 + 视觉短评（花额度）
- 需要「屏幕录制」权限。授权必须用户自己点：开启时我们只调用 `CGRequestScreenCaptureAccess`（系统弹窗）并打开系统设置对应页面，不代点。未授权时不截，提示去授权。
- 截主屏，缩到长边约 768px，JPEG 质量约 60，base64 以 `input_image` 发到 `POST /v1/responses`（沿用 `api.API_URL`、`DEFAULT_MODEL`，可由设置 `screen_model` 覆盖）。非流式，超时 30 秒。
- 实现上 `screencapture` 只能写文件，所以会在仅属本用户、权限 0700 的临时目录里短暂存在，读入内存后立即删除（finally）。
- 触发：①用户问「你看我屏幕」「看看我在干嘛」等（聊天框或气泡对话里）；②菜单「现在看一眼屏幕」；③低频主动评论（单独开关，默认关；至少 20 分钟间隔，且需切换了软件或同一窗口停留 ≥15 分钟）。

## 限频与跳过
- 默认每小时 ≤3、每天 ≤20（`screen_limit_hour`、`screen_limit_day`）。每次发起接口调用前计数（失败也计，防重试刷额度）。用完后安静，用户主动问时给出提示，不调用。
- 用量持久化：设置键 `screen_usage = {"day": "YYYY-MM-DD", "count": n, "stamps": [时间戳…]}`，跨天清零，菜单显示「今日 n/20 · 本小时 m/3」。
- 跳过（不截、不计数）：黑名单软件/标题（默认含银行、支付、密码管理器、微信/QQ/Telegram/WhatsApp/Slack/钉钉/飞书等聊天类，可通过 `screen_blacklist` 改）、全屏状态、视频类软件、密码输入框聚焦、暂停/专注中、安静时段、无屏幕录制权限、无 Key。
- 画面变化小则跳过（仅限主动评论）：16×16 灰度缩略图平均差 < 阈值。用户主动问不受此限，但受其余限制。

## 设置键（均在 `config._DEFAULTS`）
`screen_aware`(False)、`screen_vision`(False)、`screen_proactive`(False)、`screen_pause_until`(0)、`screen_quiet_hours`(False，22:00–08:00)、`screen_limit_hour`(3)、`screen_limit_day`(20)、`screen_blacklist`(None=默认)、`screen_model`(None)、`screen_usage`。

## 模块
- `screen_aware.py`：纯逻辑（分类、黑名单、限频器、静默判断、画面相似度、台词、`ScreenAwareness` 决策器；所有依赖注入，可测）。
- `screen_vision.py`：构造请求并解析响应，`post` 可注入（测试 mock）。
- `screen_mac.py`：macOS 适配（前台软件、AX 读标题/全屏/密码框、权限检查/请求、截屏缩图）。
- `screen_glue.py`：Qt 粘合（定时轮询、后台线程、气泡、「她在看」标记窗口、菜单子菜单）。
- 对既有文件的改动保持最小：`config.py`（新键）、`menu.py`（1 个字段 + 3 行）、`chat.py`（`screen_hook` 一处）、`app.py`（接线）。

## 已知限制
- 不读 `AXValue`，不读内容；全屏判断依赖辅助功能，未授权时无法判断全屏（档2 此时仍会截，建议同时授权）。
- 视觉模型沿用默认模型名，是否支持图像取决于接口；可用 `screen_model` 覆盖。
