# 桌宠grok 3D (VRM) 设计文档

日期：2026-10-10　状态：待用户审阅　范围：v1（只跑通）

## 1. 目标
把现有 2D 序列帧桌宠换成 3D 角色：AI 从认可的立绘生成 3D → 转 VRM → 在 Qt WebEngine 透明窗里用 Three.js + three-vrm 渲染，走路、转身、待机、看向鼠标。
**v1 不迁移**聊天/天气/系统监控；旧 2D 版原样保留，3D 作为独立入口：`desk_pet_grok/pet3d/` + `run3d.py`。

**成功标准**：真实迈步的走路；转身是连续旋转（无切图）；无轮廓残留；窗口透明且可拖动；透明处点击穿透。
**质量门**：模型“先出一版再评估”，不满意则停下换路线（见 §7）。

## 2. 架构（三个单元，仅通过简单接口通信）

### 单元 A：模型流水线（一次性离线脚本，`scripts/pipeline3d/`）
`front.png` → (01) 图生 3D 网格（Hunyuan3D-2 公共 Space，匿名 ZeroGPU）→ (02) 用正/背/侧立绘正交投影烘焙顶点色 → (03) Blender 无头：减面、建 VRM 人形骨架、自动权重、尾巴/头发简单骨 → (04) VRM 插件导出 `assets/model/grok.vrm` → (05) 转台预览图（`preview_mesh.py`，无需 GPU）。
- 输入：`assets/sprites/{front,side,back}.png`；输出：`.vrm` + 预览 PNG。
- 失败处理：任一步失败退出码非 0 并写 `_gen3d/*.log`；步骤间产物落盘，可单步重跑。

### 单元 B：Three.js 渲染页（`desk_pet_grok/pet3d/web/`）
`index.html` + `main.js`，用 three + @pixiv/three-vrm（本地 vendored，不走 CDN）。透明背景，正交/小视野相机，固定 30 fps。
- 动作：`walk` / `turn` / `idle` 现成片段（VRMA 或 Mixamo 重定向到 VRM 人形骨）；代码驱动：呼吸（胸/脊骨微动）、看向鼠标（头+眼，限幅）、单击蹦一下、拖动侧倾。
- 静止策略：状态为 idle 且无动画/交互时停止 `requestAnimationFrame`，保留当前帧；任何输入事件唤醒。
- 接口（Python→页面，`window.pet.*`）：
  `setState({mode:'walk'|'idle', facing:-1|1, speed})`、`lookAt(nx, ny)`（归一化 -1..1）、`hop()`、`lean(dx)`（拖动方向，-1..1）、`setSize(px)`、`setPaused(bool)`。
- 接口（页面→Python，QWebChannel `bridge`）：`ready()`、`maskReady(png_base64|rect)`（命中遮罩，见 §3）、`error(msg)`。

### 单元 C：Python 外壳（`desk_pet_grok/pet3d/`）
`window3d.py`（QWebEngineView 无边框透明置顶）、`wander3d.py`（边界与步行，复用 motion 思想但独立）、`hit.py`（命中与穿透）、`prefs.py`（位置/大小持久化）、`bridge.py`（QWebChannel）、`app3d.py`、`run3d.py`。

## 3. 点击穿透（用户硬需求 1）
- 页面每次渲染后（运行时限频 ≤10 Hz，静止时仅在变化后一次）把画布 alpha>16 的像素生成低分辨率遮罩（如 64×64 位图 / 包围矩形集合）发给 Python。
- Python 用 `QWidget.setMask(QRegion(bitmap))` 将窗口输入区域限制为角色身体；空白处由系统穿透给下层窗口，身体接收拖拽。macOS 若 setMask 对 WebEngine 无效，则退化为：鼠标移动时（全局 `QCursor.pos()` 轮询 30 Hz）查遮罩，切换 `Qt.WindowTransparentForInput`（`setWindowFlag` + `show()` 或 `NSWindow.ignoresMouseEvents` 经 PyObjC）。
- 整窗穿透开关：托盘/右键菜单“穿透模式”，开启后窗口始终 `WindowTransparentForInput`，且通过托盘可关闭（因为窗口本身收不到点击，入口只能在托盘）。状态持久化。

## 4. 位置、大小、帧率、散步、反应
- **位置/大小**：`~/Library/Application Support/desk-pet-grok/pet3d.json`：`{x,y,height}`；角色高度夹在 160–320 px（默认 220），窗口高 = 高度×1.25 以留空间；启动时若位置不在任何屏幕内则回到主屏右下。
- **帧率**：渲染锁 30 fps；idle 无动作时停渲染（见 B）。
- **散步**：用 `QScreen.availableGeometry()`（已排除任务栏/Dock）；角色脚底不得越界，边缘处转身；多屏取角色当前所在屏。步行速度与步频绑定（脚不滑）。拖动按下立即 `mode=idle` 并停步；松手后从新位置恢复（重新计时再走）。
- **三个反应（仅此三个）**：单击 → `hop()`；拖动 → `lean(dx)` 身体朝拖动方向侧倾；长时间（默认 120 s）无交互 → idle（停止散步、停渲染）。不做喂食/好感度/台词库。

## 5. 错误处理
- VRM 缺失/加载失败：页面 `error` → Python 弹托盘通知并回退提示“请运行 scripts/pipeline3d 或使用 2D 版 run.py”，不崩溃。
- WebEngine 不可用（import 失败）：`run3d.py` 打印清晰错误并以退出码 2 退出。
- 遮罩数据缺失：默认整窗可点（安全方向），并开启托盘穿透开关兜底。

## 6. 测试
- 单元（pytest，无需 Qt 显示）：`wander3d` 边界与拖动停步、`prefs` 夹取与屏外恢复、`hit` 遮罩→QRegion 转换、空闲状态机（120 s 计时用假时钟）。
- 烟测：`QT_QPA_PLATFORM=offscreen` 启动 WebEngine 加载页面（若环境支持）；`node` 级别不引入。
- 手工验收（Mac）：透明穿透、拖拽、重启记位置、托盘穿透开关、走路/转身观感。
- 流水线：`preview_mesh.py` 转台图人工评估；VRM 用 `three-vrm` 加载 smoke（页面 ready 回调）。

## 7. 风险与路线退路
1. **自动绑骨失败/变形**（Q 版身体、手臂贴身、裙子）：退路 A：用 VRoid Studio 按预览图手捏（路线二原版）；退路 B：Live2D 式 2.5D。
2. **贴图**：公共 Space 的纹理生成需 GPU 配额（匿名会超限）；v1 用立绘投影的顶点色（已验证可行，细节糊、背部/侧面有错位），不满意再做 UV 贴图烘焙。
3. **WebEngine 透明/穿透在 macOS 的差异**：见 §3 退化方案。
4. 公共 Space 可能下线/限流：脚本参数化 Space 名，备选 InstantMesh、Hunyuan3D-2mv，或用户在 Colab 运行同样脚本。
