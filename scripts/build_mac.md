# 打包 macOS（可选）

桌宠grok **不依赖** 打包也能用源码运行。要用 PyInstaller 打成 `.app` 时，参考下面。

## 前置

```bash
cd desk-pet-grok
source .venv/bin/activate
pip install "pyinstaller>=6.0"
```

## 推荐命令

在仓库根：

```bash
pyinstaller \
  --noconfirm \
  --windowed \
  --name "桌宠grok" \
  --add-data "assets:assets" \
  run.py
```

或使用仓库里的模板脚本：

```bash
bash scripts/build.sh
```

产物一般在 `dist/桌宠grok.app`（或 `dist/桌宠grok`）。

## 注意

- `--windowed`：无控制台窗口；调试时可去掉以便看日志。
- `--add-data "assets:assets"`：把立绘目录打进包；冒号左侧是源路径，右侧是包内相对路径（macOS/Linux 用 `:`，Windows 用 `;`）。
- 打包后的可执行文件若要开机自启，LaunchAgent 的 `ProgramArguments` 应指向 `.app/Contents/MacOS/桌宠grok`，而不是 `run.py`；当前「开机自启」菜单面向**源码 + venv** 场景。
- 首次打开可能被 Gatekeeper 拦：系统设置 → 隐私与安全性 → 仍要打开。
- **不要把 xAI API Key 打进包**；继续用环境变量或配置目录。

更完整的 spec 示例见仓库根 `desk-pet-grok.spec`。
