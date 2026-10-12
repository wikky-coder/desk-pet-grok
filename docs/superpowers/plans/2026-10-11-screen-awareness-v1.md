# 屏幕感知 v1 实现计划（TDD）

1. `tests/test_screen_aware.py` → `screen_aware.py`：分类、黑名单、限频器（时/日/跨天/持久化）、静默（暂停/安静时段）、画面相似度、台词均以「喵」结尾、决策器各跳过原因与成功路径（注入假 context/capture/describe/clock）。
2. `tests/test_screen_vision.py` → `screen_vision.py`：请求体含 data URL、不含窗口标题；响应解析；错误映射；Key 不进异常信息；`post` 可 mock。
3. `config.py` 新键（`tests/test_screen_config.py`）。
4. `screen_mac.py`（平台适配，非 macOS 安全返回；仅测解析函数）。
5. `screen_glue.py` + `menu.py`/`chat.py`/`app.py` 最小接线；离屏冒烟测试（有 PySide6 时）。
6. 全量 pytest、git 提交、同步到 Mac（只动相关文件，先备份，md5 校验）。
