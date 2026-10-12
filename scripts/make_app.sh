#!/bin/bash
# Build "Desk Pet Grok.app" (hand-made launcher bundle) on the Mac. Usage: scripts/make_app.sh [DEST_DIR]
# Default destination: ~/Desktop. Needs the project at ~/Desktop/desk-pet-grok with a .venv.
set -euo pipefail
PROJ="${PROJ:-$HOME/Desktop/desk-pet-grok}"
DEST="${1:-$HOME/Desktop}"
APP="$DEST/Desk Pet Grok.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/Info.plist" <<'PL'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Desk Pet Grok</string>
  <key>CFBundleDisplayName</key><string>Desk Pet Grok</string>
  <key>CFBundleIdentifier</key><string>com.desk-pet-grok.launcher</string>
  <key>CFBundleExecutable</key><string>launcher</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>LSUIElement</key><true/>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PL

cat > "$APP/Contents/MacOS/launcher" <<'SH'
#!/bin/bash
# Desk Pet Grok launcher: single instance, project venv, stderr/stdout -> ~/Library/Logs/desk-pet-grok.log
PROJ="${DESK_PET_GROK_HOME:-$HOME/Desktop/desk-pet-grok}"
LOG="$HOME/Library/Logs/desk-pet-grok.log"
mkdir -p "$HOME/Library/Logs"
running() { # python run.py started from this project (absolute or relative path, e.g. from a terminal)
  for pid in $(pgrep -f 'run\.py'); do
    cmd="$(ps -o command= -p "$pid" 2>/dev/null)"
    case "$cmd" in *python*run.py*) ;; *) continue ;; esac
    cwd="$(lsof -a -d cwd -p "$pid" -Fn 2>/dev/null | sed -n 's/^n//p')"
    if [ "$cwd" = "$PROJ" ] || [[ "$cmd" == *"$PROJ/run.py"* ]]; then return 0; fi
  done
  return 1
}
if running; then
  echo "$(date '+%F %T') already running, not starting a second instance" >> "$LOG"
  exit 0
fi
cd "$PROJ" || { echo "$(date '+%F %T') project folder missing: $PROJ" >> "$LOG"; osascript -e 'display alert "Desk Pet Grok" message "找不到项目文件夹 ~/Desktop/desk-pet-grok"'; exit 1; }
export PYTHONPATH="$PROJ"
echo "$(date '+%F %T') starting" >> "$LOG"
exec "$PROJ/.venv/bin/python" "$PROJ/run.py" >> "$LOG" 2>&1
SH
chmod +x "$APP/Contents/MacOS/launcher"

# icon: first idle frame (360x470) -> square 1024 -> iconset
TMP="$(mktemp -d)"
"$PROJ/.venv/bin/python" - "$PROJ" "$TMP/icon.png" <<'PY'
import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
app = QGuiApplication([])
proj, out = sys.argv[1], sys.argv[2]
sheet = QImage(proj + "/assets/sprites25d/idle_front.png")
fr = sheet.copy(0, 0, 360, 470)
S = 1024
canvas = QImage(S, S, QImage.Format.Format_ARGB32_Premultiplied)
canvas.fill(0)
sc = fr.scaled(int(S * 0.94 * 360 / 470), int(S * 0.94), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
p = QPainter(canvas)
p.drawImage((S - sc.width()) // 2, (S - sc.height()) // 2 + 10, sc)
p.end()
canvas.save(out)
PY
IS="$TMP/AppIcon.iconset"; mkdir -p "$IS"
for s in 16 32 128 256 512; do
  sips -z $s $s "$TMP/icon.png" --out "$IS/icon_${s}x${s}.png" >/dev/null
  sips -z $((s*2)) $((s*2)) "$TMP/icon.png" --out "$IS/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$IS" -o "$APP/Contents/Resources/AppIcon.icns"
rm -rf "$TMP"

codesign --force --deep -s - "$APP"
echo "built: $APP"
