# 桌宠 Grok（desk-pet-grok）

本机透明置顶桌宠；对话走 **xAI API**（非 SuperGrok 订阅额度）。  
Python 包名：`desk_pet_grok`。

**非官方产品。** 装饰性的 Grok / X 标识 ≠ 官方身份；本应用聊天 **不是** grok.com / Grok App / Grok Bot 同一会话。

## 功能概览

- **2.5D 人偶**（默认）：分层 rig + 预渲染 clips（idle / turn / walk）
- **趴姿 / 变体**（lounge）：躺下、伸懒腰等
- **摸摸 / 心情脸**（petting & mood）
- **贴边偷看**（cling）
- **陪做事**（work-along：看书 / 敲代码 / 终端 / 画画）
- **晃生气**（shake → 生气 → 赌气背对）
- **屏幕感知**（可选，macOS）：焦点 / 窗口边缘等
- 经典帧路径（`PetWidget` + `assets/sprites`）仍保留作回退

## 运行

需要 Python 3.11+（或当前可用的 3.x）与图形环境（PySide6）。

```bash
cd desk-pet-grok
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
PYTHONPATH=. python run.py
```

测试：`PYTHONPATH=. pytest`

可选依赖 **psutil**（已在 `requirements.txt`）：轻量 CPU / 内存提醒；未安装时跳过监控。

## API Key（务必保密）

优先环境变量 `XAI_API_KEY`；否则读**本机配置目录**下的 `xai_api_key` 文件（Unix 权限 `0600`）。

**切勿把 Key 写进仓库、提交、截图或 issues。**  
Key 不存放在项目目录内；见 `desk_pet_grok/secrets.py`。

| 平台 | 默认配置目录 |
| --- | --- |
| Windows | `%APPDATA%/desk-pet-grok` |
| macOS | `~/Library/Application Support/desk-pet-grok` |
| Linux | `~/.config/desk-pet-grok` |

也可用环境变量 `DESK_PET_GROK_CONFIG_DIR` 覆盖配置目录（测试常用）。

## 许可与素材

- **代码**：MIT（见 [LICENSE](LICENSE)）
- **角色形象 / 贴图 / 音频等素材**：由使用者自行提供或生成；本仓库中的 `assets/` 为人设演示素材，**不声称**对第三方角色或商标的权利，也**不**作为可再分发的商业素材授权。若你 fork，请替换为自己的素材。

## 文档

| 文档 | 说明 |
| --- | --- |
| [形象审计设计](docs/superpowers/specs/2026-10-09-desk-pet-grok-avatar-audit-design.md) | 角色基线、帧约定 |
| [v1 实现计划](docs/superpowers/plans/2026-10-09-desk-pet-grok-v1.md) | 早期任务拆分 |
| [精简笔记](docs/design/slim-pass-notes.md) | 仓库瘦身记录 |
