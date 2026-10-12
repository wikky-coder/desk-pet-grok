# 桌宠grok 3D (VRM) v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 3D VRM 版桌宠：图生 3D→VRM→透明 WebEngine 渲染，走路/转身/待机/看向鼠标，且点击穿透、记忆位置、边界散步。

**Architecture:** 三单元——离线模型流水线、Three.js 渲染页、Python 外壳（见 spec `docs/superpowers/specs/2026-10-10-desk-pet-grok-3d-vrm-design.md`）。3D 为独立入口 `run3d.py`，不改动 2D 代码。

**Tech Stack:** Python 3.11+, PySide6 (QtWebEngine, QtWebChannel), three.js + @pixiv/three-vrm (vendored), Blender 4.2 headless + VRM Add-on 4.7, trimesh, gradio_client, pytest.

## Global Constraints
- 角色高度夹在 160–320 px；渲染锁 30 fps；idle 静止时停渲染保留当前帧。
- 透明处不抢点击；仅角色身体接收拖拽；菜单/托盘可切整窗穿透。
- 位置与大小持久化到 `~/Library/Application Support/desk-pet-grok/pet3d.json`。
- 散步用 `availableGeometry()`，不出屏、不踩任务栏/Dock；拖动立即停步，松手从新位置继续。
- 仅三个反应：单击蹦跳、拖动侧倾、长时间无操作待机；无喂食/好感度/台词库。
- v1 不含聊天/天气/系统监控；不修改现有 2D 模块（`pet.py` 等）。
- API Key 只用环境变量，绝不写入文件。

## File Structure
- `scripts/pipeline3d/01_image_to_3d.py`（已有）、`02_project_texture.py`（已有）、`preview_mesh.py`（已有）、`03_rig_export_vrm.py`（Blender 脚本）
- `assets/model/grok.vrm`（产物）、`assets/anim/{walk,turn,idle}.vrma|glb`
- `desk_pet_grok/pet3d/{__init__,prefs,wander3d,hit,idle,bridge,window3d,app3d}.py`
- `desk_pet_grok/pet3d/web/{index.html,main.js,vendor/}`
- `run3d.py`、`tests/pet3d/test_{prefs,wander3d,hit,idle}.py`

---

### Task 1: 模型流水线可行性与 VRM 产出（风险最高，先做）
**Files:** Create `scripts/pipeline3d/03_rig_export_vrm.py`; Modify 01/02 as needed; Output `assets/model/grok.vrm`, `_gen3d/vrm_turntable.png`
**Interfaces:** Produces `assets/model/grok.vrm`（VRM 1.0，含 humanoid 骨：hips, spine, chest, neck, head, 双臂双腿，tail/hair 为额外骨）。
- [ ] Step 1: 运行 01→02，得到带顶点色网格；`preview_mesh.py` 出转台图并人工检查脸/发饰
- [ ] Step 2: Blender 无头：导入网格→减面至 ≤30k→按包围盒比例建人形骨→自动权重→导出 VRM
- [ ] Step 3: 在 Blender 里摆 T-pose/走路 pose 渲染预览，检查变形
- [ ] Step 4: 若变形不可接受：记录并停止，向用户报告并选退路（VRoid 手捏 / 2.5D）
- [ ] Step 5: Commit

### Task 2: prefs（位置/大小持久化与夹取）
**Files:** Create `desk_pet_grok/pet3d/prefs.py`; Test `tests/pet3d/test_prefs.py`
**Interfaces:** `load(path)->Prefs`, `save(path, Prefs)`, `Prefs(x:int,y:int,height:int)`, `clamp_height(h)->int`(160..320), `restore_pos(prefs, screens:list[Rect])->(x,y)`（屏外则回主屏右下）。
- [ ] Step 1: 写失败测试：`clamp_height(100)==160`、`clamp_height(999)==320`；保存后读取一致；位置在屏外 → 回主屏
- [ ] Step 2: `pytest tests/pet3d/test_prefs.py -v` 预期 FAIL
- [ ] Step 3: 实现；Step 4: 预期 PASS；Step 5: Commit

### Task 3: wander3d（边界散步与拖动停步）
**Files:** Create `desk_pet_grok/pet3d/wander3d.py`; Test `tests/pet3d/test_wander3d.py`
**Interfaces:** `Wanderer(bounds:Rect, width:int, rng)`；`tick(dt)->(x, facing, walking)`；`on_drag_start()`（立即 walking=False）；`on_drag_end(x,y)`（从新位置延时恢复）；`set_bounds(rect)`。边缘处 facing 翻转。
- [ ] Step 1: 失败测试：长时间 tick 位置恒在 bounds 内；drag_start 后 walking 为 False；drag_end 新位置后继续且在界内
- [ ] Step 2–5: FAIL→实现→PASS→Commit

### Task 4: idle 状态机（120 s 无交互待机）
**Files:** Create `desk_pet_grok/pet3d/idle.py`; Test `tests/pet3d/test_idle.py`
**Interfaces:** `IdleGate(timeout=120, clock=time.monotonic)`；`touch()`；`is_idle()->bool`；`should_render(walking, animating)->bool`（idle 且静止→False）。
- [ ] Step 1–5: 假时钟测试→实现→Commit

### Task 5: hit（遮罩→QRegion，穿透决策）
**Files:** Create `desk_pet_grok/pet3d/hit.py`; Test `tests/pet3d/test_hit.py`
**Interfaces:** `mask_from_alpha(bits:bytes,w:int,h:int,win_w:int,win_h:int)->QRegion`；`point_hits(mask, x, y)->bool`；`ClickThrough(enabled:bool)` 持久化开关。
- [ ] Step 1–5: 用小位图测试命中/未命中→实现→Commit

### Task 6: 渲染页（Three.js + three-vrm）
**Files:** Create `desk_pet_grok/pet3d/web/{index.html,main.js}`，vendor three/three-vrm；动画 `assets/anim/*`
**Interfaces:** 见 spec §2 B 的 `window.pet.*` 与 `bridge.*`。
- [ ] Step 1: 加载 `grok.vrm`，透明背景，30 fps 限帧，idle 停渲染
- [ ] Step 2: 播放 walk/idle/turn（重定向），转身为连续旋转（rotation.y 缓动）
- [ ] Step 3: 呼吸、lookAt（头+眼限幅）、hop、lean
- [ ] Step 4: 渲染后生成 64×64 alpha 遮罩上报（≤10 Hz）
- [ ] Step 5: 浏览器 offscreen 截图人工检查；Commit

### Task 7: Python 外壳（窗口、桥、入口）
**Files:** Create `window3d.py`, `bridge.py`, `app3d.py`, `run3d.py`
**Interfaces:** Consumes Tasks 2–6。托盘菜单：穿透模式、大小(小/中/大)、退出。
- [ ] Step 1: 无边框透明置顶 QWebEngineView + QWebChannel；加载页面，ready 后下发状态
- [ ] Step 2: 接 wander3d（拖动→停步）、idle 门控、prefs（移动/缩放后保存）
- [ ] Step 3: 遮罩→`setMask`；macOS 无效则轮询退化；整窗穿透开关
- [ ] Step 4: `QT_QPA_PLATFORM=offscreen` 烟测；Commit

### Task 8: 验收与同步
- [ ] Step 1: 全部 pytest 通过，2D 测试未回归
- [ ] Step 2: 同步到 `~/Desktop/desk-pet-grok`（CopyFromBox 逐文件），用户 Mac 上手工验收：穿透、拖拽、重启记位置、托盘穿透、走路/转身观感
- [ ] Step 3: Commit，README 增加 3D 启动说明 `PYTHONPATH=. python run3d.py`
