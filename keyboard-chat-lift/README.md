# Keyboard Chat Lift — Fabric 26.3 v2.1.0

This version uses the real binary IME bridge already present in the patched Zalith Launcher 2+ source branch `vanilla-chat-ime-overlay-20261015`.

The embedded Minecraft OpenJDK VM cannot directly query Android's `WindowInsets`; the paired launcher publishes actual keyboard inset and physical window height to an app-private memory-mapped file:

`/data/user/0/com.movtery.zalithlauncher.v2/files/chat-ime-state.bin`

Format: three big-endian 32-bit integers `[0x5A43494D, imeBottomPx, physicalHeightPx]`.

The mod reads this state off the render thread, then converts the measured keyboard inset into scaled Minecraft GUI coordinates and moves the real vanilla chat screen/input. No percentage guess is used. If the binary bridge is absent, the mod intentionally does not fake an automatic height; install the paired launcher build that contains `ChatImeInsetBridge`.

## Requirements
- Minecraft Java Edition 26.3
- Fabric Loader 0.19.5 or newer
- Java 25
- The paired Zalith Launcher build containing `ChatImeInsetBridge` and `installChatImeBridge()`

## Install
1. Install the paired launcher APK first.
2. Remove older Keyboard Chat Lift JARs (same mod ID).
3. Put `keyboard-chat-lift-2.1.0.jar` in the instance's `mods` folder.
4. Restart the launcher and Minecraft. Open chat and test changing keyboard height.

Build is compiled with GitHub Actions. Exact runtime behavior still requires an on-device test in Zalith.
