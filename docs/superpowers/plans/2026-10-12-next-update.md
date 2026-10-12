# 桌宠 grok 下一步更新实现计划（2026-10-12）

> **For agentic workers:** Use superpowers:subagent-driven-development or executing-plans. Checkbox steps.  
> **本计划覆盖：** 工程瘦身续作（经典路径 / interaction / screen）、分享友好度（README + 打包）、以及设计文档剩余 F8–F10 的现实切片。**只写计划，本文件提交时不实现功能。**

**Goal:** 在已公开仓库之上，先把「朋友能 clone 跑起来、测试全绿、代码再瘦一圈」做稳，再交付可双击的 macOS 包；语音与换装放到后续里程碑，不挤进本轮。

**Architecture:** 继续模块化 `desk_pet_grok`；默认运行时只保留 `Pet25D`；功能开关仍走 `config.py` + 菜单/`v4wire`；Key 永不进仓、不进包。

**Tech:** Python 3.11+、PySide6、httpx、psutil、pytest；测试像素断言补 `numpy`；打包用现有 `scripts/build.sh` / PyInstaller，签名/公证本轮只写清路径不强制完成。

**相关文档：**
- 设计：`docs/design/next-version-feature-design.md`
- 进度：`docs/design/next-version-progress.md`
- 精简：`docs/design/slim-pass-notes.md`
- 仓库：https://github.com/wikky-coder/desk-pet-grok（Public）
- 精简前备份：桌面 `desk-pet-grok-backup-pre-slim-*.tgz`（仓外，勿提交）

---

## 0. 现状快照（2026-10-12）

### 已完成（相对设计 F1–F7 + CrossPet v4）

| 项 | 状态 | 备注 |
| --- | --- | --- |
| F1 阈值可调 / 校准日志 | 完成，默认关 | 真机清单仍待 Wikky 多日试用 |
| F2 window 拆分 + 骨骼 | 完成；`rig_auto` 默认关 | 默认行为未强改 |
| F3 设置面板 / 引导 | 完成 | |
| F4 记忆 | 完成，默认关 | |
| F5 主动开口 v2 | 完成；限频默认关 | |
| F6 情绪脸 | 完成，默认关 | 仅站姿骨架待机显示 |
| F7 多种趴姿 | 完成，默认关 | stretch 为过渡姿 |
| 进度里的「F8 尾巴增强」 | 完成，`tail_boost` 默认开 | **≠ 设计文档 F8 语音**；用户暂停进一步尾巴增强，口令「继续尾巴」再开 |
| v4 全屏隐藏 / 快捷键 | 完成，默认关 | |
| v4 甩她红温 | 完成，默认关 | |
| v4 贴边扒着 | 完成，默认关 | |
| v4 陪你做事 | 完成，默认关 | 双手躯干层已修 |
| v4 时段问候 / 节日饰品 | 完成，默认开 | |
| v4 省电 | 完成，默认关 | |
| fall / fallfix2 残影 | 代码已修 + 测试 | 需真机再确认一眼 |
| 精简 Phase A/C | 完成 | bak 清理；`pet25d_paint` 抽出；`pet25d` ≈992 行 |
| GitHub / 作者 | Public；作者 Wikky | force-push 已清 weidongli；Key 扫描通过 |

### 未做 / 搁置

| 项 | 状态 |
| --- | --- |
| 设计 **F8 语音 TTS** | 未开始（P3） |
| 设计 **F9 打包/签名/检查更新** | 仅有脚本与 `build_mac.md`；无正式分发包、无应用内检查更新 |
| 设计 **F10 换装/皮肤包** | 未开始（P3） |
| 精简：砍经典 `PetWidget` + `sprites` | 搁置（测试仍依赖） |
| 精简：再瘦 `interaction.py`（≈559 行） | 搁置 |
| 精简：合并 `screen_*` / probe | 搁置（职责尚清，不强行乱并） |
| `numpy` | **不在** `requirements.txt`；fallfix / happyface / edgefit / tail / workhands 等测试会 skip 或失败 |

### 运行时默认（无 Key 仍可用）

本地：走动、摸头、气泡台词、2.5D、时段问候、节日饰品（后两项默认开）。  
需 Key：聊天、识屏备注、记忆摘要等。

### 文件体量（运行时重点）

```text
pet25d.py      ~992
chat.py        ~813
pet.py         ~672   ← 经典路径，待删
interaction.py ~559
lines.py       ~482
window.py      ~423
screen_*+probe ~1271 合计（6 文件，职责不同）
```

---

## 1. 本轮目标（建议 1 个短里程碑 ≈ 数天工作量）

**产品口号：**「朋友打开 README 能跑；你自己维护更轻松；有空再打 `.app` 给人。」

1. **工程健康（P0）**：测试迁完 → 删经典路径；`interaction` 按域拆 mixin；`numpy` 进依赖；README 写清「无 Key 基础功能」。
2. **分享与分发（P1）**：打通「源码路径」与「双击 `.app` 路径」文档/脚本；不做完整公证也可先出 unsigned 试用包说明。
3. **新功能切片（P2，可选）**：只开 **F9 轻量检查更新**（读 GitHub release / 版本号提示）；**不做** F8 语音、**不做** F10 换装。

---

## 2. 建议文件地图（本轮会动到的）

```text
desk-pet-grok/
  README.md                          # 朋友向：clone / 无 Key / 有 Key
  requirements.txt                   # + numpy
  docs/design/slim-pass-notes.md     # 续记 Phase D/E
  docs/design/next-version-progress.md  # 本轮收尾时补一节
  docs/superpowers/plans/2026-10-12-next-update.md  # 本文件
  desk_pet_grok/
    window.py          # 去掉 PetWidget 回退（Phase D 末）
    pet.py             # 删除或缩成兼容壳后删除
    interaction.py     # 拆出 work/cling/anger/greet/power/mood…
    interaction_*.py   # 新建按域 mixin（见 Task B）
    screen_*.py        # 仅文档化边界；合并仅在确认死代码后
  tests/
    test_pet_assets.py / test_pet_sprites.py / test_puppet_window.py  # 迁到 25d 或删
  scripts/
    build.sh / build_mac.md / make_app.sh  # 朋友向打包说明对齐
  assets/sprites/      # Phase D 通过后可移出仓或大幅删减（~31MB）
```

---

## 3. 明确不做（本轮）

- [ ] **不实现 F8 语音 TTS**（麦克风、常驻监听更不做）。
- [ ] **不实现 F10 换装商城/皮肤包框架**（除非 Wikky 改口优先）。
- [ ] **不继续尾巴增强**（等口令「继续尾巴」）。
- [ ] **不花 xAI 额度生成新立绘**（本轮以代码/文档/打包为主）。
- [ ] **不把 `_archives/`、`_gen*`、本机路径、Key、备份 tarball 推进仓**。
- [ ] **不强行合并** 仍有独立职责的 `screen_aware` / `screen_vision` / `screen_mac` / `ax_probe` / `focus_probe`（先画依赖图，有死代码再删）。
- [ ] **不在本轮改默认开关大翻转**（例如强开 `rig_auto` / `mood`）；分享友好靠文档说明即可。

---

## 4. 优先级与推荐顺序

```text
P0-1  Task A  numpy + 测试基线全绿
P0-2  Task B  迁经典路径测试 → 删 PetWidget / sprites（可分两提交）
P0-3  Task C  拆薄 interaction.py
P0-4  Task D  README 朋友向打磨 + 无 Key 冒烟清单
P1    Task E  打包路径对齐（PyInstaller / make_app 说明）+ 可选 unsigned 试包
P2    Task F  轻量「检查更新」（可选；依赖 E 有版本号）
P3+   以后    F8 语音 → F10 皮肤；screen 族精简；继续尾巴
```

**原则：** 先瘦身与可分享，再新功能。P0 全部完成前不开始 F8/F10。

---

## 5. 任务拆解（可勾选、可测）

### Task A: 测试依赖补全（numpy）— P0

**Files:**
- Modify: `requirements.txt`
- Verify: `tests/test_fallfix.py`, `test_fallfix2.py`, 及依赖 numpy 的 happyface / edgefit / tail / workhands

- [ ] **Step 1:** 在 `requirements.txt` 增加 `numpy>=1.26`（或与现有环境对齐的下限）。
- [ ] **Step 2:** `pip install -r requirements.txt` 后跑  
  `PYTHONPATH=. pytest tests/test_fallfix.py tests/test_fallfix2.py -q`  
  Expected: 通过（不再因缺 numpy skip/fail）。
- [ ] **Step 3:** 全量 `PYTHONPATH=. pytest -q`；记录通过数；提交  
  `chore: add numpy for pixel assertion tests`。

---

### Task B: 迁测试并移除经典 `PetWidget` 路径 — P0

**背景：** `window.py` 在 `puppet25d` 假或素材缺失时仍 `PetWidget`；`tests/test_pet_assets.py`、`test_pet_sprites.py`、`test_puppet_window.py`（`puppet25d=False`）锁住旧路径；`assets/sprites` ≈31MB。

**Files:**
- Modify: 上述测试 → 断言 `Pet25D` / `puppet_available()` 行为
- Modify: `window.py`（始终 25d；素材缺失时占位 + 日志，不再实例化 `PetWidget`）
- Delete or gut: `desk_pet_grok/pet.py`（确认无其它 import）
- Optional later: 从 git 移除 `assets/sprites/`（另提交，方便 revert）

- [ ] **Step 1:** 列出所有 `PetWidget` / `puppet25d=False` / `assets/sprites` 引用（源码+测试+脚本）。
- [ ] **Step 2:** 改写测试：缺 25d 素材时的行为改为「安全降级/明确错误」，不再测经典帧动画。
- [ ] **Step 3:** 跑相关测试全绿后，改 `window.py` 去掉 `PetWidget` 分支；删 `pet.py` 或留一版期弃用警告一版（推荐直接删，历史在 git）。
- [ ] **Step 4:** 全量 pytest；真机启动确认默认桌宠仍为 25d。
- [ ] **Step 5:** 提交 `refactor: drop classic PetWidget fallback`；可选第二提交 `chore: remove assets/sprites`。
- [ ] **Step 6:** 更新 `docs/design/slim-pass-notes.md` Phase D。

**验收：** 仓库不再 import `PetWidget`；默认启动路径只有 `Pet25D`；测试全绿；README 去掉「经典帧回退」表述。

---

### Task C: 拆薄 `interaction.py` — P0

**背景：** 单 mixin 含 work / greet / holiday / power / cling / anger / tail / lounge_variants / mood / petting / lounge…，tick 由 `motion_driver` 调用。

**建议拆分（每个文件一个域，仍 mixin 进 `PetWindow`）：**

```text
interaction.py          # 保留：petting + lounge 开关/探测 + 对外薄封装
interaction_work.py     # work_along
interaction_cling.py    # cling_edge
interaction_anger.py    # shake_anger
interaction_social.py   # time_greeting + holiday_outfit
interaction_power.py    # power_save
interaction_mood.py     # mood + tail_boost 开关（小）
```

- [ ] **Step 1:** 先写/改一个域的测试（例如 `test_workfix` / `test_powersave`）确认 import 路径。
- [ ] **Step 2:** 一次只搬一个域；每搬完跑相关测试 + 全量一次。
- [ ] **Step 3:** `motion_driver` / `menu` / `v4wire` / `settings_panel` 的调用点保持方法名不变（拆的是文件，不是 API）。
- [ ] **Step 4:** 目标：`interaction.py` &lt; ~250 行；提交  
  `refactor: split interaction mixin by domain`。

**验收：** 行为开关与设置键不变；相关测试通过；无循环 import。

---

### Task D: README 朋友向打磨 — P0

**Files:** `README.md`（可链到 `scripts/build_mac.md`）

- [ ] **Step 1:** 文首加「30 秒了解」：无 API Key 也能用的功能列表；有 Key 才解锁的列表。
- [ ] **Step 2:** Clone 步骤保持简短；注明 macOS 为主、需图形界面；Windows 尽力。
- [ ] **Step 3:** 强调 Key 只放环境变量/配置目录；**禁止**贴 Key 到 issue。
- [ ] **Step 4:** 删或改「经典帧仍保留」——与 Task B 同步。
- [ ] **Step 5:** 可选：加「常见问题」Gatekeeper / 辅助功能 / 无声（没 Key）三条。
- [ ] **Step 6:** 提交 `docs: README for public clone without API key`。

**验收：** 不熟悉项目的人只读 README 能跑起来并知道为什么聊天不工作。

---

### Task E: 打包路径对齐（F9 轻量）— P1

**现状：** `scripts/build.sh`（PyInstaller）、`scripts/make_app.sh`（启动器指向本机 `~/Desktop/desk-pet-grok`）、`scripts/build_mac.md`。`make_app` **不能**直接送给朋友（绑本机路径）。

- [ ] **Step 1:** 文档写清两条路径：  
  A) 开发者/朋友：源码 + venv（推荐）；  
  B) 分发：`build.sh` → `dist/桌宠grok.app`（含 assets）。
- [ ] **Step 2:** 检查 PyInstaller `--add-data` 是否覆盖 `assets/rig25d`、`lounge25d`、`cling25d`、`festival25d`、`work25d`、`shake25d` 等运行所需目录（不仅是顶层 `assets`）。
- [ ] **Step 3:** 本机打一次 unsigned 包，冷启动冒烟（无 Key：走动/摸头/气泡；有 Key 可选）。
- [ ] **Step 4:** README 增加「下载 .app」注意事项：Gatekeeper、Key 仍走配置目录、体积预期。
- [ ] **Step 5:** **本轮不做** Apple 公证/稳定签名身份（记为 F9 后续）；在 progress 里记 D9 风险仍在。
- [ ] **Step 6:** 提交 `docs+scripts: align packaging path for sharing`（若改了脚本）。

**验收：** 另一台 Mac（或干净用户）按文档能在 ≤10 分钟内看到桌宠（源码路径）；若提供 .app，双击可启动且不内嵌 Key。

---

### Task F（可选）: 应用内「检查更新」— P2

**设计对齐 F9 的「只提示，不自动替换」。**

- [ ] **Step 1:** 定版本源：`desk_pet_grok/__init__.py` 的 `__version__` + GitHub `latest release` API（公开仓可读）。
- [ ] **Step 2:** 菜单「检查更新…」→ 气泡/对话框显示当前 vs 最新；失败时安静提示网络问题。
- [ ] **Step 3:** 不下载安装包、不自动替换；测试 mock HTTP。
- [ ] **Step 4:** 提交 `feat: check-for-updates menu (notify only)`。

若时间不够，本轮可只做 Task E，把 F 留到下一迭代。

---

### Task G（延后清单，写入 progress 即可）

- [ ] Screen 族：画依赖图；确认无死文件再合并。
- [ ] F8 TTS：候选引擎（系统 `say` / 云 TTS）；默认关；与气泡同步；预算与延迟验收按设计文档。
- [ ] F10：角色包目录约定（rig + eyes + lines prefix）；一个发色测试包。
- [ ] 「继续尾巴」：用户口令后再开尾巴增强迭代。
- [ ] 真机附录 A 清单与 fallfix2 目视确认。

---

## 6. 成功标准（本轮结束时）

- [ ] `pytest` 全绿（含原 numpy 相关用例）。
- [ ] 无 `PetWidget` 经典回退；或明确文档说明为何仍保留（若 Task B 未做完则不得声称「已删」）。
- [ ] `interaction.py` 显著变薄或已拆文件，方法 API 兼容。
- [ ] README 使朋友无 Key 也能理解并运行基础功能。
- [ ] 打包文档与脚本一致；Key 扫描在每次发布提交前再跑一遍。
- [ ] 未实现的 F8/F10 在 `next-version-progress.md` 仍标记未开始，避免编号与「尾巴 F8」混淆（建议 progress 改称「尾巴增强」勿再标 F8）。

---

## 7. 风险与注意

| 风险 | 缓解 |
| --- | --- |
| 删经典路径导致某测试/脚本裸奔 | Task B Step 1 全库引用表；分两提交 |
| mixin 拆分循环 import | 域文件只依赖 window 协议（duck typing）；重逻辑保持无 Qt |
| PyInstaller 漏素材 | 冷启动检查 lounge/cling/fest/work |
| 公开仓误提交本机路径/Key | 提交前扫描 `weidongli`、`/Users/`、`xai-*`、`.local` |
| 朋友期望「安装即聊天」 | README 明确无 Key = 本地桌宠 |

---

## 8. 执行时给代理的约束

1. 小步提交；每任务可独立 revert。  
2. 不改用户本机 `settings.json` 里的个人开关。  
3. 作者保持 **Wikky** + GitHub noreply。  
4. 实现前若与本计划冲突，先改计划再写代码。  
5. 用户说「继续尾巴」才动尾巴；说「做语音/换装」再开 F8/F10。

---

## 9. 给 Wikky 的一句话优先级

**先：** numpy → 砍经典路径 → 拆 interaction → README。  
**再：** 能给人用的 `.app` 说明/试包。  
**后：** 检查更新；语音与换装等口令。
