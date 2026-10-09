#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINE="${1:-engine}"
APP_DIR="$ENGINE/app_pojavlauncher"
GRADLE_FILE="$APP_DIR/build.gradle"
PREFS_FILE="$APP_DIR/src/main/java/net/kdt/pojavlaunch/prefs/LauncherPreferences.java"
VIDEO_PREF="$APP_DIR/src/main/res/xml/pref_video.xml"
MANIFEST="$APP_DIR/src/main/AndroidManifest.xml"
MAIN_MENU="$APP_DIR/src/main/java/net/kdt/pojavlaunch/fragments/MainMenuFragment.java"
LAYOUT_DIR="$APP_DIR/src/main/res/layout"
DRAWABLE_DIR="$APP_DIR/src/main/res/drawable"

for file in "$GRADLE_FILE" "$PREFS_FILE" "$VIDEO_PREF" "$MANIFEST" "$MAIN_MENU"; do
    [[ -f "$file" ]] || { echo "Required upstream file missing: $file" >&2; exit 2; }
done
mkdir -p "$LAYOUT_DIR" "$DRAWABLE_DIR"

cp "$ROOT/minecraft-pc-launcher/overlay/app_pojavlauncher/src/main/res/layout/fragment_launcher.xml" "$LAYOUT_DIR/fragment_launcher.xml"
cp "$ROOT/minecraft-pc-launcher/overlay/app_pojavlauncher/src/main/res/drawable/launcher_hero_card.xml" "$DRAWABLE_DIR/launcher_hero_card.xml"
cp "$ROOT/minecraft-pc-launcher/overlay/app_pojavlauncher/src/main/res/drawable/launcher_nav_item_bg.xml" "$DRAWABLE_DIR/launcher_nav_item_bg.xml"
cp "$ROOT/minecraft-pc-launcher/overlay/app_pojavlauncher/src/main/res/drawable/launcher_icon.xml" "$DRAWABLE_DIR/launcher_icon.xml"

python3 - "$GRADLE_FILE" "$PREFS_FILE" "$VIDEO_PREF" "$MANIFEST" "$MAIN_MENU" <<'PY'
from pathlib import Path
import sys

gradle, prefs, video, manifest, menu = map(Path, sys.argv[1:])

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
    raise SystemExit("Could not find renderer default in LauncherPreferences.java")
prefs.write_text(prefs_text.replace(old_prefs, new_prefs))

video_text = video.read_text()
old_default = 'android:defaultValue="opengles2"'
new_default = 'android:defaultValue="opengles_sfpew"'
if old_default not in video_text:
    raise SystemExit("Could not find renderer default in pref_video.xml")
video.write_text(video_text.replace(old_default, new_default, 1))

manifest_text = manifest.read_text()
manifest_text = manifest_text.replace('android:icon="@mipmap/ic_launcher"', 'android:icon="@drawable/launcher_icon"')
manifest_text = manifest_text.replace('android:roundIcon="@mipmap/ic_launcher_round"', 'android:roundIcon="@drawable/launcher_icon"')
if 'android:icon="@drawable/launcher_icon"' not in manifest_text:
    raise SystemExit("Could not set custom app icon")
manifest.write_text(manifest_text)

# Point built-in launcher links to Minecraft's own website, not the engine project.
menu_text = menu.read_text()
news_old = 'mNewsButton.setOnClickListener(v -> Tools.openURL(requireActivity(), Tools.URL_HOME));'
news_new = 'mNewsButton.setOnClickListener(v -> Tools.openURL(requireActivity(), "https://www.minecraft.net/en-us/articles"));'
community_old = 'mDiscordButton.setOnClickListener(v -> Tools.openURL(requireActivity(), getString(R.string.social_media_invite)));'
community_new = 'mDiscordButton.setOnClickListener(v -> Tools.openURL(requireActivity(), "https://www.minecraft.net/en-us"));'
if news_old not in menu_text:
    raise SystemExit("Could not find upstream news-button handler")
if community_old not in menu_text:
    raise SystemExit("Could not find upstream community-button handler")
menu_text = menu_text.replace(news_old, news_new).replace(community_old, community_new)

# Add Installations and Skins actions wired to the existing profile/editor backend and
# Minecraft account skin management page.
binding_old = 'mVersionSpinner = view.findViewById(R.id.mc_version_spinner);'
binding_new = binding_old + '\n\n        Button mInstallationsButton = view.findViewById(R.id.installations_button);\n        Button mSkinsButton = view.findViewById(R.id.skins_button);\n        Button mPatchNotesButton = view.findViewById(R.id.patch_notes_button);\n        Button mAccountsButton = view.findViewById(R.id.accounts_button);\n        Button mSettingsShortcutButton = view.findViewById(R.id.settings_shortcut_button);'
if binding_old not in menu_text:
    raise SystemExit("Could not find version spinner binding")
menu_text = menu_text.replace(binding_old, binding_new, 1)

listener_old = 'mEditProfileButton.setOnClickListener(v -> mVersionSpinner.openProfileEditor(requireActivity()));'
listener_new = listener_old + '\n        mInstallationsButton.setOnClickListener(v -> mVersionSpinner.performClick());\n        mSkinsButton.setOnClickListener(v -> Tools.openURL(requireActivity(), "https://www.minecraft.net/en-us/msaprofile/mygames/editskin"));\n        mPatchNotesButton.setOnClickListener(v -> Tools.openURL(requireActivity(), "https://feedback.minecraft.net/hc/en-us/sections/360001186971-Release-Changelogs"));\n        mAccountsButton.setOnClickListener(v -> requireActivity().findViewById(R.id.account_spinner).performClick());\n        mSettingsShortcutButton.setOnClickListener(v -> requireActivity().findViewById(R.id.setting_button).performClick());'
if listener_old not in menu_text:
    raise SystemExit("Could not find profile-editor listener")
menu_text = menu_text.replace(listener_old, listener_new, 1)
menu.write_text(menu_text)

print("Launcher overlay applied; namespace preserved; MobileGlues-compatible renderer, news/site links, installations, accounts, settings, skins, and patch notes actions configured.")
PY

echo "Overlay and branding patches applied to temporary engine checkout: $ENGINE"
