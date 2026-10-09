#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINE="${1:-engine}"
GRADLE_FILE="$ENGINE/app_pojavlauncher/build.gradle"
LAYOUT_DIR="$ENGINE/app_pojavlauncher/src/main/res/layout"
DRAWABLE_DIR="$ENGINE/app_pojavlauncher/src/main/res/drawable"

[[ -f "$GRADLE_FILE" ]] || { echo "Engine not found: $GRADLE_FILE" >&2; exit 2; }
mkdir -p "$LAYOUT_DIR" "$DRAWABLE_DIR"

cp "$ROOT/minecraft-pc-launcher/overlay/app_pojavlauncher/src/main/res/layout/fragment_launcher.xml" "$LAYOUT_DIR/fragment_launcher.xml"
cp "$ROOT/minecraft-pc-launcher/overlay/app_pojavlauncher/src/main/res/drawable/launcher_hero_card.xml" "$DRAWABLE_DIR/launcher_hero_card.xml"
cp "$ROOT/minecraft-pc-launcher/overlay/app_pojavlauncher/src/main/res/drawable/launcher_nav_item_bg.xml" "$DRAWABLE_DIR/launcher_nav_item_bg.xml"

python3 - "$GRADLE_FILE" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()

# Keep the upstream namespace/package for compiled R and source references.
# Rebrand only the installed application ID and runtime authority/resource values.
replacements = [
    ('applicationId "net.kdt.pojavlaunch"', 'applicationId "net.efxd29.minecraftlauncher"'),
    ('"PojavLauncher (Debug)"', '"Minecraft Launcher (Debug)"'),
    ('"PojavLauncher (Minecraft: Java Edition for Android)"', '"Minecraft Launcher"'),
    ('"PojavLauncher (Nightly)"', '"Minecraft Launcher (Nightly)"'),
    ('"PojavLauncher"', '"Minecraft Launcher"'),
    ("'net.kdt.pojavlaunch.pub.scoped.gamefolder'", "'net.efxd29.minecraftlauncher.pub.scoped.gamefolder'"),
    ("'net.kdt.pojavlaunch.scoped.gamefolder.debug'", "'net.efxd29.minecraftlauncher.scoped.gamefolder.debug'"),
    ("'net.kdt.pojavlaunch.scoped.gamefolder'", "'net.efxd29.minecraftlauncher.scoped.gamefolder'"),
    ("'net.kdt.pojavlaunch.pub'", "'net.efxd29.minecraftlauncher.pub'"),
    ("'net.kdt.pojavlaunch.debug'", "'net.efxd29.minecraftlauncher.debug'"),
    ("'application_package', 'net.kdt.pojavlaunch'", "'application_package', 'net.efxd29.minecraftlauncher'"),
]
for old, new in replacements:
    if old not in text:
        print(f"NOTE: upstream Gradle value not found: {old}")
    text = text.replace(old, new)

if "namespace 'net.kdt.pojavlaunch'" not in text:
    raise SystemExit("Unexpected upstream namespace: expected net.kdt.pojavlaunch to remain unchanged")
path.write_text(text)
print("Launcher overlay applied; internal namespace preserved.")
PY

echo "Overlay copied into temporary engine checkout: $ENGINE"
