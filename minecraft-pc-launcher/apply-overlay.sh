#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINE="${1:-engine}"
APP_DIR="$ENGINE/app_pojavlauncher"
GRADLE_FILE="$APP_DIR/build.gradle"
PREFS_FILE="$APP_DIR/src/main/java/net/kdt/pojavlaunch/prefs/LauncherPreferences.java"
VIDEO_PREF="$APP_DIR/src/main/res/xml/pref_video.xml"
MANIFEST="$APP_DIR/src/main/AndroidManifest.xml"
LAYOUT_DIR="$APP_DIR/src/main/res/layout"
DRAWABLE_DIR="$APP_DIR/src/main/res/drawable"

[[ -f "$GRADLE_FILE" ]] || { echo "Engine not found: $GRADLE_FILE" >&2; exit 2; }
[[ -f "$PREFS_FILE" && -f "$VIDEO_PREF" && -f "$MANIFEST" ]] || { echo "Expected upstream launcher preference/manifest files missing" >&2; exit 2; }
mkdir -p "$LAYOUT_DIR" "$DRAWABLE_DIR"

cp "$ROOT/minecraft-pc-launcher/overlay/app_pojavlauncher/src/main/res/layout/fragment_launcher.xml" "$LAYOUT_DIR/fragment_launcher.xml"
cp "$ROOT/minecraft-pc-launcher/overlay/app_pojavlauncher/src/main/res/drawable/launcher_hero_card.xml" "$DRAWABLE_DIR/launcher_hero_card.xml"
cp "$ROOT/minecraft-pc-launcher/overlay/app_pojavlauncher/src/main/res/drawable/launcher_nav_item_bg.xml" "$DRAWABLE_DIR/launcher_nav_item_bg.xml"
cp "$ROOT/minecraft-pc-launcher/overlay/app_pojavlauncher/src/main/res/drawable/launcher_icon.xml" "$DRAWABLE_DIR/launcher_icon.xml"

python3 - "$GRADLE_FILE" "$PREFS_FILE" "$VIDEO_PREF" "$MANIFEST" <<'PY'
from pathlib import Path
import sys

gradle, prefs, video, manifest = map(Path, sys.argv[1:])

# Rebrand the installed application without changing the namespace used by source/R.
text = gradle.read_text()
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
gradle.write_text(text)

# Prefer SFPEW/MobileGlues for fresh installs. SFPEW wraps MobileGlues and is the
# upstream option explicitly offered for all Minecraft versions; renderer setup
# retains upstream fallback behavior for unsupported devices.
prefs_text = prefs.read_text()
old_prefs = 'DEFAULT_PREF.getString("renderer", "opengles2")'
new_prefs = 'DEFAULT_PREF.getString("renderer", "opengles_sfpew")'
if old_prefs not in prefs_text:
    raise SystemExit("Could not find the default renderer in LauncherPreferences.java")
prefs.write_text(prefs_text.replace(old_prefs, new_prefs))

video_text = video.read_text()
old_default = 'android:defaultValue="opengles2"'
new_default = 'android:defaultValue="opengles_sfpew"'
if old_default not in video_text:
    raise SystemExit("Could not find the default renderer in pref_video.xml")
video.write_text(video_text.replace(old_default, new_default, 1))

manifest_text = manifest.read_text()
manifest_text = manifest_text.replace('android:icon="@mipmap/ic_launcher"', 'android:icon="@drawable/launcher_icon"')
manifest_text = manifest_text.replace('android:roundIcon="@mipmap/ic_launcher_round"', 'android:roundIcon="@drawable/launcher_icon"')
if 'android:icon="@drawable/launcher_icon"' not in manifest_text:
    raise SystemExit("Could not set the custom application icon")
manifest.write_text(manifest_text)

print("Launcher overlay applied; internal namespace preserved; fresh installs default to the upstream SFPEW/MobileGlues renderer.")
PY

echo "Overlay copied and launcher branding/preferences patched in temporary engine checkout: $ENGINE"
