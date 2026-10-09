# 桌宠grok

本机透明置顶桌宠；对话走 **xAI API**（非 SuperGrok 订阅额度）。  
Python 包名：`desk_pet_grok`；工程目录：`desk-pet-grok`。

**非官方产品。** 装饰性的 Grok / X 标识 ≠ 官方身份；本应用聊天 **不是** grok.com / Grok App / Grok Bot 同一会话。

## 运行

需要本机 Python 3.11+（或当前可用的 3.x）与图形环境（PySide6）。

```bash
cd desk-pet-grok
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
PYTHONPATH=. python run.py
```

已在仓库根激活 venv 时，同样可用：`PYTHONPATH=. python run.py`。

测试：`PYTHONPATH=. pytest`

## 可选依赖

- **psutil**（已列入 `requirements.txt`）：用于轻量 CPU / 内存提醒。未安装时桌宠照常运行，仅跳过系统监控。


## API Key

优先环境变量 `XAI_API_KEY`；否则读配置目录下的 `xai_api_key` 文件（Unix 权限 `0600`）。  
**切勿把 Key 写进仓库或提交。**

配置目录名：`desk-pet-grok`

| 平台 | 默认路径 |
| --- | --- |
| Windows | `%APPDATA%/desk-pet-grok` |
| macOS | `~/Library/Application Support/desk-pet-grok` |
| Linux | `~/.config/desk-pet-grok` |

测试可设 `DESK_PET_GROK_CONFIG_DIR` 覆盖。Key 在 [console.x.ai](https://console.x.ai) 申请；与 SuperGrok 订阅无关。

## 角色与素材（摘要）

- **基线**：金发猫娘 Q 版；白底徽章黑 **X** 发卡；Grok 斜杠圆环项链；女仆风短裙。素材由用户提供，**实现者不得改写立绘**。
- **序列**：每状态目标 6–8 帧、最低 4 帧；约 2–6 fps（idle/sleep 偏低，work 偏高）。画布建议 412×344，耳/尾/发卡距边 ≥8%。
- **状态**：流式回复 **首字到达后离开 `think`**，改用 `idle` 轻循环 + 气泡；缺图回退 `idle` 并提示，空则占位圆。

细节见 [`assets/README.md`](assets/README.md)。

## 文档

| 文档 | 说明 |
| --- | --- |
| [形象审计设计](docs/superpowers/specs/2026-10-09-desk-pet-grok-avatar-audit-design.md) | 角色基线、帧约定、品牌边界（素材约定源） |
| [v1 实现计划](docs/superpowers/plans/2026-10-09-desk-pet-grok-v1.md) | 任务拆分与验收顺序 |
| [assets/README.md](assets/README.md) | 文件夹命名、帧数/fps、回退规则 |

v1 范围：聊天桌宠 + 占位/序列播放。工具能力（剪贴板、打开 URL 等）留到后续版本。

## 开机自启

托盘 / 右键菜单勾选 **开机自启**：

| 平台 | 机制 |
| --- | --- |
| macOS | `~/Library/LaunchAgents/com.desk-pet-grok.plist`（优先用项目 `.venv` 的 Python + `run.py`） |
| Windows | `HKCU\...\Run` 值 `DeskPetGrok`（无 `winreg` 时跳过） |
| Linux | `~/.config/autostart/desk-pet-grok.desktop` |

设置会额外写入配置目录 `settings.json` 的 `autostart` 字段。取消勾选即删除上述条目。

## 打包（可选）

源码运行即可；若要打成独立应用，见：

- [`scripts/build_mac.md`](scripts/build_mac.md)
- [`scripts/build.sh`](scripts/build.sh)
- [`desk-pet-grok.spec`](desk-pet-grok.spec)

按需安装 PyInstaller；CI **不必** 默认跑打包。

